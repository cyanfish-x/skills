---
name: weekly-report
description: 生成中文工作周报。自动识别当前工作区的 git 仓库与本机 git 账户，读取其上周（或指定区间）的提交记录，按业务功能模块分组，合并润色成一份简短的中文周报。这是个人通用 skill，不绑定特定项目，切换工作区后自动适配。在用户说"写周报""生成周报""本周/上周工作总结""weekly report"等时使用。周报按项目分节，编号条目格式，正文以代码块输出。
---

# Weekly Report（周报生成）

## 用途

这是一个**个人通用 skill**：自动识别**当前工作区**的 git 仓库和本机 git 账户，读取上周（或指定区间）提交，按项目分节合并润色成简短中文周报。不绑定特定项目结构，切换工作区即可用。

## 工作流程

### 1. 自动定位仓库与作者（无需手填）

- **仓库**支持两种模式：
  - **单仓库**（默认）：仓库 = 当前工作目录。脚本默认在当前目录运行，自动读取该目录所属的 git 仓库。若用户指定了其它仓库路径，用 `--repo <路径>` 传入。
  - **多仓库**（`--repo-dir <工作区根>`）：递归发现该目录下所有 git 仓库并批量采集，**推荐用于 `D:\work` 这类多项目工作区**。自动缓存仓库列表加速二次运行，对每个仓库做廉价探测门控（只读 HEAD 一个对象）排除区间内无活动的仓库，再并行采集活跃仓库。详见下方「缓存」。
- **作者 = 本机 git 账户**。脚本自动读取 `git config user.email` / `user.name`。
- 注意：不要假设仓库结构或模块名。一切由脚本在运行时自动识别。

### 2. 采集并按模块分组（运行脚本）

运行 `scripts/gather_weekly_commits.py`：抓取提交、过滤 merge、用**通用启发式**按业务模块归类、输出 JSON。

默认范围 = **上一自然周（周一~周日）**。模块提取启发式自动适配：monorepo（packages/apps/services）、前端（src/pages、views、modules）、Next.js（src/app）、通用 `src/<m>/` 等。

常用参数：

```bash
# 默认：当前工作区 + 上一自然周 + 自动作者
python scripts/gather_weekly_commits.py

# 多仓库：扫描工作区下所有 git 仓库（推荐用于多项目工作区）
python scripts/gather_weekly_commits.py --repo-dir D:/work
python scripts/gather_weekly_commits.py --repo-dir D:/work --no-cache   # 禁用缓存
python scripts/gather_weekly_commits.py --repo-dir D:/work --jobs 4

# 本自然周 / 最近 N 天 / 指定区间
python scripts/gather_weekly_commits.py --week this
python scripts/gather_weekly_commits.py --days 7
python scripts/gather_weekly_commits.py --since 2026-07-06 --until 2026-07-12

# 指定仓库 / 作者
python scripts/gather_weekly_commits.py --repo /path/to/repo
python scripts/gather_weekly_commits.py --author zhang@xx.com
python scripts/gather_weekly_commits.py --author 张三 --author-by name

# 项目结构特殊、启发式不准时，用正则覆盖（需含1个捕获组）
python scripts/gather_weekly_commits.py --module-regex 'com/(\w+)/'
```

脚本 **stdout 输出 JSON**（机器读取），stderr 输出一行人可读摘要。只解析 stdout 的 JSON。脚本路径相对本 skill 目录：`scripts/gather_weekly_commits.py`。

JSON 结构关键字段：

- `range`：时间区间与标签（`since`/`until`/`label`）。
- `author_name`：本机 git 账户姓名。
- `groups[].key`：模块名（从路径提取的目录名，可能英文/拼音/缩写）或 `common`/`other`。
- `groups[].kind`：`module`（业务模块）/ `common`（公共基础）/ `other`（其他）。
- `groups[].commits[]`：`{hash, date, subject, files}`。

**多仓库模式**（`--repo-dir`）的 JSON 外层不同：顶层有 `mode: "multi"`、`repo_dir`、`cached`、`scanned_repos`（发现的仓库总数）、`active_repos`（区间内有提交的仓库数），`repos[]` 数组每项含 `{repo, total_commits, groups}`，其中 `groups` 结构与单仓库一致。撰写周报时遍历 `repos[]`，每个活跃仓库按项目分节即可。

### 3. 撰写周报

读取 `references/report_guide.md` 获取：模块名→中文名的通用推断法、撰写要点、输出格式与周报模板。关键规则：

- **模块名转中文**：优先用 commit message 里的中文业务词；目录名是英文/拼音时合理翻译（详见 references 的对照表）；拿不准就保留原 key，**不要杜撰**。
- **分项目编号汇报**：每个活跃仓库一节 `【项目中文名】`，条目按（1）（2）… 编号，模块/功能名用「」标注；单项目 3~6 条。
- **合并润色**：同一功能多次提交合并为一条，去重，动宾短句（"完成/修复/优化…"开头，子项用"、"和"及"连接），不照搬 commit 列表。
- **简短客观**：每条一行，只写已完成的工作。

### 4. 输出

把周报正文**整体放进代码块**呈现给用户：每条独立成行、条目间不空行。原因：Markdown 软换行会把连续行合并成一段，代码块才能保住换行，也便于直接复制。若用户要求保存为文件，再写入；否则不落盘。

## 缓存与性能（仅多仓库模式）

`--repo-dir` 模式针对"每周跑一次"的高频场景做了两层加速，在工作区根目录生成缓存文件 `.weekly-report-cache.json`：

**两层加速（实测 45 仓库工作区：冷启动 1.1s → 缓存命中 0.6s）**：
1. **缓存仓库列表，命中时跳过全量 walk**。`os.walk` 遍历大工作区是真正的大头（占冷启动 50%+）。缓存命中时只校验缓存里的路径仍存在 + 扫顶层目录补入新增仓库，跳过全量遍历。深层新仓库会在下次缓存未命中时被全量 walk 收录，不会永久遗漏。
2. **文件系统预筛，探测阶段零 git spawn**。判断"区间内有没有活动"不靠 `git log -1`（spawn 45 次子进程），而是直接读 `.git/logs/HEAD`（reflog）末行时间戳；reflog 缺失时回退到 refs 文件 mtime；都拿不到则保守视为活跃。拿不准一律视为活跃——预筛是优化，绝不漏内容。

**只缓存仓库列表，不缓存别的**：提交数据每次必须重新探测（跨周不可信）；git 账户是瞬时查询，缓存反而有陈旧风险。

**其他特性**：
- **工作区级隔离**：缓存文件跟随工作区，不污染 skill 目录。切换工作区互不干扰，符合"通用 skill 不绑定项目"的定位。
- **健壮回退**：缓存文件缺失、JSON 损坏或版本不符时静默回退全量 walk，不报错。
- **可禁用/重建**：`--no-cache` 强制全量发现（调试用）；删除缓存文件即重建。

## 脚本依赖

- 需要 `git` 可在命令行调用；脚本默认在当前工作目录运行。
- 仅用 Python 标准库，无需安装第三方包。
