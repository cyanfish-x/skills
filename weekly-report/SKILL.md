---
name: weekly-report
description: 生成中文工作周报。自动识别当前工作区的 git 仓库与本机 git 账户，读取其上周（或指定区间）的提交记录，按业务功能模块分组，合并润色成一份简短的中文周报。这是个人通用 skill，不绑定特定项目，切换工作区后自动适配。在用户说"写周报""生成周报""本周/上周工作总结""weekly report"等时使用。功能开发按模块分节汇报。
---

# Weekly Report（周报生成）

## 用途

这是一个**个人通用 skill**：自动识别**当前工作区**的 git 仓库和本机 git 账户，读取上周（或指定区间）提交，按业务功能模块分组，合并润色成简短中文周报。不绑定特定项目结构，切换工作区即可用。

## 工作流程

### 1. 自动定位仓库与作者（无需手填）

- **仓库 = 当前工作目录**。脚本默认在当前目录运行，自动读取该目录所属的 git 仓库。若用户指定了其它仓库路径，用 `--repo <路径>` 传入。
- **作者 = 本机 git 账户**。脚本自动读取 `git config user.email` / `user.name`。
- 注意：不要假设仓库结构或模块名。一切由脚本在运行时自动识别。

### 2. 采集并按模块分组（运行脚本）

运行 `scripts/gather_weekly_commits.py`：抓取提交、过滤 merge、用**通用启发式**按业务模块归类、输出 JSON。

默认范围 = **上一自然周（周一~周日）**。模块提取启发式自动适配：monorepo（packages/apps/services）、前端（src/pages、views、modules）、Next.js（src/app）、通用 `src/<m>/` 等。

常用参数：

```bash
# 默认：当前工作区 + 上一自然周 + 自动作者
python scripts/gather_weekly_commits.py

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

### 3. 撰写周报

读取 `references/report_guide.md` 获取：模块名→中文名的通用推断法、撰写要点、周报模板。关键规则：

- **模块名转中文**：优先用 commit message 里的中文业务词；目录名是英文/拼音时合理翻译（详见 references 的对照表）；拿不准就保留原 key，**不要杜撰**。
- **按模块分节**：每个 `kind=module` 分组写一节；`common` 写成"公共/基础优化"，`other` 写成"其他"。
- **合并润色**：同一模块多条提交合并为 1~3 条，去重，用动宾短句，不照搬 commit 列表。
- **简短客观**：整份周报 ≤15 行；只写已完成的工作。

### 4. 输出

直接把周报正文呈现给用户（使用周报模板格式）。若用户要求保存为文件，再写入；否则不落盘。

## 脚本依赖

- 需要 `git` 可在命令行调用；脚本默认在当前工作目录运行。
- 仅用 Python 标准库，无需安装第三方包。
