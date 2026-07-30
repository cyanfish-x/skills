#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按功能模块采集"本机 git 账户"在当前仓库指定时间范围内的提交，输出 JSON。

默认范围 = 上一个自然周（周一~周日）。作者默认自动读取本机 git 账户。

用法:
    python gather_weekly_commits.py                       # 上一自然周 + 自动作者
    python gather_weekly_commits.py --week this           # 本自然周
    python gather_weekly_commits.py --days 7              # 最近 7 天
    python gather_weekly_commits.py --since 2026-07-06 --until 2026-07-12
    python gather_weekly_commits.py --author zhang@xx.com --author-by email
    python gather_weekly_commits.py --repo /path/to/repo

输出(JSON)结构:
{
  "repo": "...", "author_name": "...", "author_email": "...",
  "range": {"since": "2026-07-06", "until": "2026-07-12", "label": "上一自然周"},
  "total_commits": N,
  "groups": [
    {"key":"costPrice","kind":"module","commits":[{"hash","date","subject","files"}]},
    {"key":"common","kind":"common","commits":[...]}
  ]
}
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta

# 提交块分隔符：选用几乎不会出现在 commit message 里的字符串
SEP = "===COMMIT===\n"


def run_git(args, repo):
    """调用 git 子命令，失败时打印错误并退出。"""
    result = subprocess.run(
        ["git", "-C", repo] + args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        sys.stderr.write("[git 错误] " + result.stderr.strip() + "\n")
        sys.exit(1)
    return result.stdout


def read_account(repo):
    """读取本机 git 账户的 name 和 email。"""
    email = run_git(["config", "user.email"], repo).strip()
    name = run_git(["config", "user.name"], repo).strip()
    return name, email


def pick_author(name, email, author_arg, author_by):
    """决定用于 git log --author 的过滤值。"""
    if author_arg:
        return author_arg
    if author_by == "name":
        return name or email
    # 默认优先 email（更唯一），email 为空时回退 name
    return email or name


def week_range(target):
    """计算 target 所在自然周的周一与周日。"""
    monday = target - timedelta(days=target.weekday())  # weekday() 周一=0
    sunday = monday + timedelta(days=6)
    return monday, sunday


def compute_range(args):
    """根据参数解析出 (since, until, label)。"""
    today = date.today()
    if args.since and args.until:
        return args.since, args.until, f"{args.since} ~ {args.until}"
    if args.days is not None:
        until = today
        since = today - timedelta(days=args.days - 1)
        return since, until, f"最近 {args.days} 天"
    if args.week == "this":
        monday, sunday = week_range(today)
        return monday, sunday, "本自然周"
    # 默认：上一自然周
    this_monday, _ = week_range(today)
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday, "上一自然周"


# 业务模块的"明确边界"正则：命中即归为 module（优先于 common 检查）。
# 这些路径约定本身就是模块划分，即便内部含 api/components 等也视作该模块的一部分。
# 捕获组只匹配字母开头的段，避免把 Next.js 路由组 (auth)、Java 包前缀 com/ 等当模块名。
#   - monorepo:   packages/<pkg>/ | apps/<app>/ | services/<svc>/
#   - 前端:       src/pages/<m>/ | src/views/<m>/ | src/modules/<m>/
#   - Next.js:    src/app/<m>/ | app/<m>/ （跳过 _ 与 ( 开头的保留段/路由组）
_MODULE_BOUNDARIES = [
    r"(?:^|/)(?:packages|apps|services)/([A-Za-z][\w-]*)/",
    r"(?:^|/)src/(?:pages|views|modules)/([A-Za-z][\w-]*)/",
    r"(?:^|/)(?:src/)?app/(?![_(])([A-Za-z][\w-]*)/",
]
# 兜底模块正则：在排除 common 之后，把 src/<m>/ 视为模块。
# 不做"顶层 <m>/"兜底，以免把 Java 包前缀(com/、org/)等误判为模块；
# 纯顶层划分的项目（无 src/）可用 --module-regex 显式指定。
_MODULE_FALLBACK = [
    r"(?:^|/)src/([A-Za-z][\w-]*)/",
]
# 公共/基础路径特征：这些目录的改动视为通用基础设施而非业务模块
_COMMON_PATTERNS = (
    "/api/", "/apis/", "/components/", "/component/", "/utils/", "/util/",
    "/helpers/", "/common/", "/shared/", "/core/", "/config/", "/configs/",
    "/lib/", "/libs/", "/internal/", "/pkg/", "/store/", "/stores/",
    "/hooks/", "/composables/", "/router/", "/routes/", "/middleware/",
    "/types/", "/interfaces/", "/constants/", "/assets/", "/styles/",
    "/test/", "/tests/", "/__tests__/", "/public/", "/static/", "/locales/",
    "/i18n/", "/build/", "/scripts/", "/tools/",
)
# 根级配置文件（归为 common）
_COMMON_FILES = {
    "package.json", "pnpm-workspace.yaml", "lerna.json", "turbo.json",
    "tsconfig.json", "jsconfig.json", "vite.config.ts", "vite.config.js",
    "vue.config.js", "webpack.config.js", "next.config.js", "nuxt.config.ts",
    ".gitignore", "pnpm-lock.yaml", "package-lock.json", "yarn.lock",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "pyproject.toml", "requirements.txt", "setup.py",
    "Dockerfile", "docker-compose.yml", "Makefile", "CMakeLists.txt",
}


def classify_path(path, module_regex=None):
    """根据文件路径归类：(kind, key)。
    kind: module=业务模块 / common=公共基础 / other=无法归类。

    匹配优先级（高→低）：
      1. 用户提供的 module_regex（覆盖一切，适配特殊结构）
      2. 明确的模块边界（monorepo / 前端 pages,views,modules / Next.js app）
      3. 公共基础目录或根配置文件 -> common
      4. 兜底：通用 src/<m>/ 或顶层 <m>/ -> module
      5. other
    这样 src/api/、src/components/ 会被正确归为 common，而非误判为模块。
    """
    p = path.replace("\\", "/")

    # 1. 用户显式正则（最高优先级）
    if module_regex:
        m = re.search(module_regex, p)
        if m and m.groups():
            return "module", m.group(1)

    # 2. 明确的模块边界
    for pattern in _MODULE_BOUNDARIES:
        m = re.search(pattern, p)
        if m:
            return "module", m.group(1)

    # 3. 公共/基础目录 或 根级配置文件
    if any(pat in p for pat in _COMMON_PATTERNS):
        return "common", "common"
    if p.rsplit("/", 1)[-1] in _COMMON_FILES:
        return "common", "common"

    # 4. 兜底：通用 src/<m>/ 或顶层 <m>/
    for pattern in _MODULE_FALLBACK:
        m = re.search(pattern, p)
        if m:
            return "module", m.group(1)

    # 5. 其他
    return "other", "other"


def parse_log(raw):
    """解析 `git log --pretty=format:SEP... --name-only` 的输出为提交列表。"""
    commits = []
    for block in raw.split(SEP):
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.split("\n")
        # 首行格式: <hash>|<date>|<subject>，限制分割 2 次以兼容 subject 含 '|'
        head = lines[0].split("|", 2)
        if len(head) < 3:
            continue
        hash_, cdate, subject = head[0].strip(), head[1].strip(), head[2].strip()
        files = [ln.strip() for ln in lines[1:] if ln.strip()]
        commits.append({
            "hash": hash_,
            "date": cdate,
            "subject": subject,
            "files": files,
        })
    return commits


def group_commits(commits, module_regex=None):
    """按功能模块分组。优先级：业务模块 > 公共基础 > 其他。
    一个提交只归入其最高优先级的分类，避免在多个分组中重复计数
    （周报按"功能模块"汇报，不应把同一条工作重复列在多个模块下）。
    若同时涉及多个业务模块，则归入其中每一个（跨模块的同一项工作）。
    module_regex: 透传给 classify_path，覆盖启发式（用于结构特殊的项目）。
    """
    groups = {}  # key -> {"kind":..,"commits":[...]}

    def add(kind, key, commit):
        g = groups.setdefault(key, {"kind": kind, "key": key, "commits": []})
        # kind 以首次登记为准；避免同 key 被 other 覆盖 module
        if g["kind"] == "other" and kind != "other":
            g["kind"] = kind
        g["commits"].append(commit)

    for c in commits:
        kinds = {classify_path(f, module_regex) for f in c["files"]} if c["files"] else {("other", "other")}
        module_keys = [k for kind, k in kinds if kind == "module"]
        if module_keys:
            # 涉及业务模块时，只归业务模块，不再算 common/other
            for key in module_keys:
                add("module", key, c)
        elif ("common", "common") in kinds:
            add("common", "common", c)
        else:
            add("other", "other", c)

    # 排序：业务模块在前(common/other 靠后)，组内按日期升序
    order = {"module": 0, "common": 1, "other": 2}
    result = sorted(groups.values(), key=lambda g: (order.get(g["kind"], 9), g["key"]))
    for g in result:
        g["commits"].sort(key=lambda c: (c["date"], c["hash"]))
    return result


def main():
    ap = argparse.ArgumentParser(description="采集并按模块分组 git 提交，输出 JSON 供周报撰写。")
    ap.add_argument("--repo", default=".", help="git 仓库路径（默认当前目录）")
    ap.add_argument("--author", help="作者过滤值（name 或 email），默认自动读取本机 git 账户")
    ap.add_argument("--author-by", choices=["email", "name"], default="email",
                    help="自动读取作者时优先用 email(默认) 还是 name")
    ap.add_argument("--week", choices=["last", "this"], default="last", help="自然周范围（默认 last=上一自然周）")
    ap.add_argument("--days", type=int, help="使用最近 N 天覆盖自然周范围")
    ap.add_argument("--since", help="起始日期 YYYY-MM-DD（需与 --until 同时使用）")
    ap.add_argument("--until", help="结束日期 YYYY-MM-DD（需与 --since 同时使用）")
    ap.add_argument("--module-regex", dest="module_regex",
                    help="覆盖默认启发式的模块正则（含1个捕获组），用于结构特殊的项目。"
                         "例：r'src/(\\w+)/' 或 'com/(\\w+)/'")
    args = ap.parse_args()

    name, email = read_account(args.repo)
    author = pick_author(name, email, args.author, args.author_by)
    if not author:
        sys.stderr.write("[错误] 未识别到 git 账户，请用 --author 指定，或先 git config user.email。\n")
        sys.exit(1)

    since, until, label = compute_range(args)
    since_dt = f"{since} 00:00:00"
    until_dt = f"{until} 23:59:59"

    # 拉取提交（过滤 merge 提交），格式: SEP + hash|date|subject，后跟文件清单
    raw = run_git([
        "log", "--no-merges",
        f"--since={since_dt}",
        f"--until={until_dt}",
        f"--author={author}",
        "--date=short",
        f"--pretty=format:{SEP}%h|%ad|%s",
        "--name-only",
    ], args.repo)

    commits = parse_log(raw)
    groups = group_commits(commits, args.module_regex)

    output = {
        "repo": args.repo,
        "author_name": name,
        "author_email": email,
        "author_filter": author,
        "range": {
            "since": str(since),
            "until": str(until),
            "label": label,
        },
        "total_commits": len(commits),
        "groups": groups,
    }

    # 友好的 stderr 摘要（便于人眼快速确认），stdout 只输出 JSON
    sys.stderr.write(
        f"[完成] {label} {since} ~ {until} | 作者={author} | "
        f"提交={len(commits)} | 分组={len(groups)}\n"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
