#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按功能模块采集"本机 git 账户"在指定时间范围内的提交，输出 JSON。

支持两种模式：
  - 单仓库（默认 / --repo）：采集当前目录或指定仓库，输出单仓库 JSON。
  - 多仓库（--repo-dir）：递归发现目录下所有 git 仓库，缓存仓库列表、
    廉价探测门控 + 并行采集，只汇总区间内有提交的仓库。

默认范围 = 上一个自然周（周一~周日）。作者默认自动读取本机 git 账户。

用法:
    # 单仓库（行为与旧版完全一致）
    python gather_weekly_commits.py
    python gather_weekly_commits.py --repo /path/to/repo

    # 多仓库：扫描工作区下所有 git 仓库
    python gather_weekly_commits.py --repo-dir D:/work
    python gather_weekly_commits.py --repo-dir D:/work --week this
    python gather_weekly_commits.py --repo-dir D:/work --no-cache   # 禁用缓存
    python gather_weekly_commits.py --repo-dir D:/work --jobs 4

    # 时间范围 / 作者
    python gather_weekly_commits.py --week this
    python gather_weekly_commits.py --days 7
    python gather_weekly_commits.py --since 2026-07-06 --until 2026-07-12
    python gather_weekly_commits.py --author zhang@xx.com

输出(JSON)结构（单仓库）:
  {
    "repo": "...", "author_name": "...", "author_email": "...",
    "range": {"since": "...", "until": "...", "label": "..."},
    "total_commits": N,
    "groups": [
      {"key":"costPrice","kind":"module","commits":[{"hash","date","subject","files"}]},
      {"key":"common","kind":"common","commits":[...]}
    ]
  }

输出(JSON)结构（多仓库）:
  {
    "mode":"multi", "repo_dir":"...", "cached":true,
    "author_name":"...", "author_email":"...",
    "range":{"since":"...","until":"...","label":"..."},
    "scanned_repos":N, "active_repos":M,
    "repos":[ {"repo":"...","total_commits":N,"groups":[...]} ]
  }
"""
import argparse
import json
import os
import re
import subprocess
import sys

# Windows 默认 stdout 编码（cp936/mbcs）无法可靠输出任意 Unicode（含中文路径/commit），
# 强制 UTF-8。reconfigure 在 Python 3.7+ 可用；旧版本静默回退（保持原行为）。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

# 提交块分隔符：选用几乎不会出现在 commit message 里的字符串
SEP = "===COMMIT===\n"

# 缓存文件版本号，schema 变化时递增以作兼容
CACHE_VERSION = 1
# 缓存文件名（存在 repo-dir 根目录下，工作区级隔离）
CACHE_FILENAME = ".weekly-report-cache.json"

# 仓库发现时跳过的目录（通用 I/O 黑名单，不做任何业务过滤）
_SKIP_DIRS = {
    "node_modules", "dist", "build", ".venv", "venv", "env",
    ".git", ".svn", ".hg", ".idea", ".vscode",
    "__pycache__", ".next", ".nuxt", ".cache", ".turbo",
    "target", "bin", "obj",
}


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


def run_git_soft(args, repo):
    """调用 git 子命令，失败时返回 None（用于批量探测，单仓库失败不中断整体）。"""
    try:
        result = subprocess.run(
            ["git", "-C", repo] + args,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
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


# ───────────────────────── 缓存 ─────────────────────────

def cache_path_for(repo_dir):
    """缓存文件路径：始终落在 repo-dir 根目录下，工作区级隔离。"""
    return os.path.join(repo_dir, CACHE_FILENAME)


def load_cache(path):
    """读取缓存。文件缺失/JSON 损坏/版本不符时返回 None，不报错。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return None
    repos = data.get("repos")
    if not isinstance(repos, list):
        return None
    return repos


def save_cache(path, repo_dir, repos):
    """覆盖写缓存。失败时静默（缓存只是加速，不能影响功能）。"""
    data = {
        "version": CACHE_VERSION,
        "repo_dir": os.path.abspath(repo_dir),
        "repos": sorted(repos),
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ───────────────────────── 仓库发现 ─────────────────────────

def walk_git_repos(root, max_depth=6):
    """递归发现 root 下所有 git 仓库（含 .git 的目录）。
    跳过通用 I/O 黑名单目录（node_modules/dist/.venv 等），不做任何业务过滤。
    max_depth 限制递归层级，避免极端深层目录。
    返回仓库绝对路径的列表。
    """
    repos = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # 计算相对深度，超限则不再下钻
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            # 到达深度上限：不再进入任何子目录
            dirnames[:] = []
            continue
        # 先检测是否为仓库根（剪枝会从 dirnames 移除 .git，必须在剪枝之前判断）
        if ".git" in dirnames or ".git" in filenames:
            repos.append(dirpath)
            # .git 所在目录视为仓库根，不再下钻（避免进入 .git/ 内部）
            dirnames[:] = []
            continue
        # 再剪枝：原地修改 dirnames 以跳过黑名单目录（os.walk 推荐的剪枝方式）
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
    return repos


def discover_repos(repo_dir, use_cache):
    """发现仓库列表。缓存命中时跳过昂贵的全量 walk，只做轻量校验+增量补扫。
    返回 (repos, cache_hit: bool)。

    策略权衡：全量 walk 在大工作区（数百目录）要几百毫秒，而周报每周跑一次、
    仓库结构很少变。因此：
      - 缓存未命中/禁用：全量 walk + 校验，写缓存。
      - 缓存命中：跳过 walk，只校验缓存里的路径仍存在；同时轻量扫顶层目录
        补入新增仓库（应对新建项目）。校验失败的（已删除）从缓存剔除。
    """
    repo_dir = os.path.abspath(repo_dir)
    cache_path = cache_path_for(repo_dir)

    cached = load_cache(cache_path) if use_cache else None

    # 缓存命中：跳过全量 walk，只做轻量校验 + 顶层增量补扫
    if cached:
        repos = _validate_cached(cached) + _scan_shallow_new(repo_dir, cached)
        repos = sorted(set(repos))
        if use_cache:
            save_cache(cache_path, repo_dir, repos)
        return repos, True

    # 缓存未命中：全量 walk
    found = walk_git_repos(repo_dir)
    if use_cache:
        save_cache(cache_path, repo_dir, found)
    return found, False


def _validate_cached(cached):
    """校验缓存里的路径仍是 git 仓库。失效的（已删除/移走）剔除。"""
    valid = []
    for p in cached:
        git_dir = os.path.join(p, ".git")
        if os.path.isdir(git_dir) or os.path.isfile(git_dir):  # worktree 的 .git 是文件
            valid.append(p)
    return valid


def _scan_shallow_new(repo_dir, known):
    """轻量增量补扫：只扫 repo_dir 直接子目录一层，发现不在缓存里的新仓库。
    周报场景下绝大多数新项目会直接放在工作区根下，一层足够；深层新仓库
    会在下次缓存未命中时被全量 walk 收录，不会永久遗漏。
    """
    known_set = set(known)
    new_repos = []
    try:
        entries = os.listdir(repo_dir)
    except OSError:
        return new_repos
    for entry in entries:
        sub = os.path.join(repo_dir, entry)
        if sub in known_set or not os.path.isdir(sub):
            continue
        git_dir = os.path.join(sub, ".git")
        if os.path.isdir(git_dir) or os.path.isfile(git_dir):
            new_repos.append(sub)
    return new_repos


# ───────────────────────── 廉价探测门控 ─────────────────────────
# 目的：快速排除"区间内肯定没活动"的仓库，避免对沉睡仓库跑昂贵的
#   git log --author --since --until --name-only 全量采集。
# 实现：优先用纯文件系统判断（零 git spawn），拿不准时保守视为活跃，
#   交由后续完整采集兜底——预筛是优化，宁可多跑也不能漏内容。

# 失败时返回的"无限大"哨兵：表示"探测不到，保守视为活跃"，绝不漏报。
TS_UNKNOWN = float("inf")


def _resolve_git_dir(repo):
    """定位仓库的 .git 目录（兼容 worktree 的 .git 文件）。返回路径或 None。"""
    git_path = os.path.join(repo, ".git")
    if os.path.isdir(git_path):
        return git_path
    # worktree / submodule：.git 是个文件，内含 "gitdir: <path>"
    if os.path.isfile(git_path):
        try:
            with open(git_path, "r", encoding="utf-8", errors="replace") as f:
                line = f.readline().strip()
            if line.startswith("gitdir:"):
                resolved = line.split(":", 1)[1].strip()
                if not os.path.isabs(resolved):
                    resolved = os.path.join(repo, resolved)
                if os.path.isdir(resolved):
                    return resolved
        except OSError:
            return None
    return None


def probe_latest_ts_fs(repo):
    """纯文件系统探测仓库最近活动时间戳（unix 秒），零 git spawn。
    多级回退，拿不准时返回 TS_UNKNOWN（视为活跃，绝不漏报）：

      1. .git/logs/HEAD 末行时间戳（reflog，记录 commit/pull/checkout）
      2. .git/refs/** 与 .git/packed-refs 的 mtime 最大值（reflog 禁用时）
      3. 都拿不到 → 返回 +∞，视为活跃，交由完整采集兜底
    """
    git_dir = _resolve_git_dir(repo)
    if not git_dir:
        return TS_UNKNOWN

    # 1. reflog：每行格式 "<old> <new> <作者> <unix时间戳> <时区>\\t<描述>"
    head_log = os.path.join(git_dir, "logs", "HEAD")
    try:
        with open(head_log, "rb") as f:
            # 只读末尾一小段，避免超大 reflog 全量读取
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 512))
            tail = f.read()
        # 反向找最后一个换行后的完整行
        lines = tail.split(b"\n")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            # reflog 行: <40hash> <40hash> <ident> <ts> <tz>\t<msg>
            parts = line.split(b" ")
            if len(parts) >= 4:
                try:
                    ts = int(parts[-2])  # 倒数第二是时间戳，最后是时区
                    if ts > 0:
                        return ts
                except ValueError:
                    continue
            break  # 末行解析失败，放弃 reflog 走回退
    except OSError:
        pass

    # 2. 回退：refs 文件 + packed-refs 的 mtime 最大值
    max_mtime = -1
    refs_dir = os.path.join(git_dir, "refs")
    for base, _dirs, files in os.walk(refs_dir):
        for fn in files:
            try:
                m = os.path.getmtime(os.path.join(base, fn))
                if m > max_mtime:
                    max_mtime = m
            except OSError:
                continue
    packed = os.path.join(git_dir, "packed-refs")
    try:
        m = os.path.getmtime(packed)
        if m > max_mtime:
            max_mtime = m
    except OSError:
        pass

    if max_mtime > 0:
        return int(max_mtime)

    # 3. 都拿不到：保守视为活跃
    return TS_UNKNOWN


def to_unix_ts(d):
    """date → unix 时间戳（本地时区）。"""
    return int(datetime(d.year, d.month, d.day).timestamp())


def filter_active_by_probe(repos, since_ts):
    """廉价门控：只保留最近活动时间 >= since_ts 的仓库。
    用纯文件系统探测（读 reflog/refs mtime），零 git spawn。
    对 45 个小文件串行读取也极快（毫秒级），无需并行。
    """
    active = []
    for r in repos:
        if probe_latest_ts_fs(r) >= since_ts:
            active.append(r)
    return active


# ───────────────────────── 单仓库采集 ─────────────────────────

def gather_repo(repo, author, since_dt, until_dt):
    """采集单个仓库的提交并分组。返回 dict（含 total_commits / groups）。"""
    raw = run_git([
        "log", "--no-merges",
        f"--since={since_dt}",
        f"--until={until_dt}",
        f"--author={author}",
        "--date=short",
        f"--pretty=format:{SEP}%h|%ad|%s",
        "--name-only",
    ], repo)
    commits = parse_log(raw)
    groups = group_commits(commits)
    return {"total_commits": len(commits), "groups": groups}


def gather_repo_soft(repo, author, since_dt, until_dt):
    """gather_repo 的容错版：单仓库失败不中断批量。"""
    try:
        return gather_repo(repo, author, since_dt, until_dt)
    except SystemExit:
        return {"total_commits": 0, "groups": [], "error": "git failed"}
    except Exception as e:
        return {"total_commits": 0, "groups": [], "error": str(e)}


# ───────────────────────── 主入口 ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description="采集并按模块分组 git 提交，输出 JSON 供周报撰写。")
    ap.add_argument("--repo", default=".", help="单仓库模式：git 仓库路径（默认当前目录）")
    ap.add_argument("--repo-dir", dest="repo_dir",
                    help="多仓库模式：递归发现该目录下所有 git 仓库并批量采集。"
                         "缓存文件 .weekly-report-cache.json 会写在该目录下。")
    ap.add_argument("--no-cache", dest="no_cache", action="store_true",
                    help="禁用缓存（强制全量仓库发现，调试用）")
    ap.add_argument("--timing", action="store_true",
                    help="多仓库模式输出各阶段耗时到 stderr（调试/性能分析用）")
    ap.add_argument("--jobs", type=int, default=min(8, (os.cpu_count() or 4) + 4),
                    help="多仓库模式并行度（默认 min(8, cpu+4)）")
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

    # 多仓库模式
    if args.repo_dir:
        run_multi(args)
    else:
        run_single(args)


def run_single(args):
    """单仓库模式：行为与旧版完全一致。"""
    repo = args.repo
    name, email = read_account(repo)
    author = pick_author(name, email, args.author, args.author_by)
    if not author:
        sys.stderr.write("[错误] 未识别到 git 账户，请用 --author 指定，或先 git config user.email。\n")
        sys.exit(1)

    since, until, label = compute_range(args)
    since_dt = f"{since} 00:00:00"
    until_dt = f"{until} 23:59:59"

    raw = run_git([
        "log", "--no-merges",
        f"--since={since_dt}",
        f"--until={until_dt}",
        f"--author={author}",
        "--date=short",
        f"--pretty=format:{SEP}%h|%ad|%s",
        "--name-only",
    ], repo)

    commits = parse_log(raw)
    groups = group_commits(commits, args.module_regex)

    output = {
        "repo": repo,
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
    sys.stderr.write(
        f"[完成] {label} {since} ~ {until} | 作者={author} | "
        f"提交={len(commits)} | 分组={len(groups)}\n"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


def run_multi(args):
    """多仓库模式：发现 + 缓存 + 廉价探测 + 并行采集，输出汇总 JSON。"""
    from datetime import datetime as _dt  # 局部引用，避免顶部 import 冲突
    import time as _time

    repo_dir = args.repo_dir
    if not os.path.isdir(repo_dir):
        sys.stderr.write(f"[错误] --repo-dir 不是有效目录: {repo_dir}\n")
        sys.exit(1)

    timing = {}  # 阶段 -> 秒；仅 --timing 时打印
    T = _time.perf_counter

    use_cache = not args.no_cache
    t0 = T()
    repos, cache_hit = discover_repos(repo_dir, use_cache)
    t1 = T()
    timing["discover_repos"] = t1 - t0

    if not repos:
        sys.stderr.write(f"[完成] 未在 {repo_dir} 下发现 git 仓库\n")
        print(json.dumps({
            "mode": "multi",
            "repo_dir": os.path.abspath(repo_dir),
            "cached": cache_hit,
            "author_name": "", "author_email": "",
            "range": {"since": "", "until": "", "label": ""},
            "scanned_repos": 0, "active_repos": 0,
            "repos": [],
        }, ensure_ascii=False, indent=2))
        return

    # 用第一个仓库读账户（作者过滤值），其它仓库沿用同一账户。
    # 注：若各仓库账户不同，建议 --author 显式指定。
    t2 = T()
    name, email = read_account(repos[0])
    author = pick_author(name, email, args.author, args.author_by)
    t3 = T()
    timing["read_account"] = t3 - t2
    if not author:
        sys.stderr.write("[错误] 未识别到 git 账户，请用 --author 指定，或先 git config user.email。\n")
        sys.exit(1)

    since, until, label = compute_range(args)
    since_dt = f"{since} 00:00:00"
    until_dt = f"{until} 23:59:59"
    since_ts = to_unix_ts(since)

    sys.stderr.write(
        f"[扫描] 仓库={len(repos)}（缓存{'命中' if cache_hit else '未命中/禁用'}）"
        f" | 廉价探测中...\n"
    )

    # 廉价门控：先排除最近活动早于 since 的仓库（纯文件系统探测，零 git spawn）
    t4 = T()
    active_repos = filter_active_by_probe(repos, since_ts)
    t5 = T()
    timing["probe_fs"] = t5 - t4
    sys.stderr.write(
        f"[扫描] 活跃候选={len(active_repos)}（区间内可能有提交的仓库）"
        f" | 并行采集 {label} {since} ~ {until} | 作者={author}\n"
    )

    # 并行采集（只有活跃候选才跑昂贵查询）
    t6 = T()
    results = []
    if active_repos:
        if len(active_repos) == 1 or args.jobs <= 1:
            for r in active_repos:
                results.append((r, gather_repo_soft(r, author, since_dt, until_dt)))
        else:
            with ThreadPoolExecutor(max_workers=min(args.jobs, len(active_repos))) as ex:
                future_map = {ex.submit(gather_repo_soft, r, author, since_dt, until_dt): r
                              for r in active_repos}
                for fut in as_completed(future_map):
                    results.append((future_map[fut], fut.result()))
    t7 = T()
    timing["gather"] = t7 - t6

    # 只保留有提交的仓库，按路径稳定排序
    repo_outputs = []
    for r, data in sorted(results, key=lambda x: x[0]):
        if data.get("total_commits", 0) > 0:
            repo_outputs.append({
                "repo": r,
                "total_commits": data["total_commits"],
                "groups": data["groups"],
            })

    output = {
        "mode": "multi",
        "repo_dir": os.path.abspath(repo_dir),
        "cached": cache_hit,
        "author_name": name,
        "author_email": email,
        "author_filter": author,
        "range": {
            "since": str(since),
            "until": str(until),
            "label": label,
        },
        "scanned_repos": len(repos),
        "active_repos": len(repo_outputs),
        "repos": repo_outputs,
    }
    sys.stderr.write(
        f"[完成] {label} {since} ~ {until} | 作者={author} | "
        f"扫描={len(repos)} | 活跃={len(repo_outputs)}\n"
    )
    # 各阶段耗时（仅 --timing）。discover=仓库发现(缓存命中跳过walk)，
    # read_account=读git账户, probe_fs=文件系统预筛, gather=采集活跃仓库提交。
    if args.timing:
        total = sum(timing.values())
        order = ["discover_repos", "read_account", "probe_fs", "gather"]
        lines = []
        for k in order:
            v = timing.get(k, 0)
            pct = (v / total * 100) if total else 0
            lines.append(f"  {k:<14} {v*1000:7.1f} ms  ({pct:4.1f}%)")
        sys.stderr.write(
            f"[计时] 总计 {total*1000:.1f} ms\n" + "\n".join(lines) + "\n"
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
