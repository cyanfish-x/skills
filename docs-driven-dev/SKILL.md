---
name: docs-driven-dev
description: >-
  文档驱动 Agent 开发工作流：初始化 docs/{intent,spec,adr}，安全处理老项目目录冲突，
  按三类变更强制同步文档，可选从代码生成带「推测」标记的重建草稿（须确认后落盘）。
  Use when the user mentions 文档驱动、初始化文档、同步文档、ADR、docs/intent、docs/spec、
  从代码重建文档，or when changing user-facing behavior, product scope, or architecture
  decisions that should be recorded in project docs.
---

# 文档驱动 Agent 开发

跨项目可复用。改代码前先读相关文档；行为/意图/架构变更必须同步文档。禁止「先写代码再补文档」。

## 何时使用

- 初始化或补齐 `docs/` 文档体系
- 改用户可感知行为、产品意图/范围、架构取舍
- 老项目接入本工作流（含目录冲突）
- 可选：从现有代码重建文档草稿

**不要用：** 纯样式/文案/重构且行为不变、且现有 spec 未写到相关细节时——可不写文档。

## 文档根与索引约定

默认根：

| 角色 | 默认路径 |
|------|----------|
| 总索引 | `docs/index.md` |
| 意图 | `docs/intent/` |
| 行为规格 | `docs/spec/` |
| 架构决策 | `docs/adr/` |

- **索引等价：** 某目录已有承担索引职责的 `README.md` 时，视同 `index.md`，**不要**再新建重复的 `index.md`；仅当两者皆无时创建 `index.md`。
- **路径映射：** 冲突后若改用其它根（如 `docs/agent/{intent,spec,adr}`），必须写入总索引中的「文档根路径」表；后续会话**先读该表**再读写文档。
- 模板源文件在本 Skill 的 [templates/](templates/)；复制到目标仓库时按下方规则，**不覆盖**已有文件。

## 模式分流

1. **初始化** → 「初始化流程」
2. **日常开发**（含用户未提初始化但要改行为/意图/架构）→ 若文档根未就绪，**先初始化**；完成前不写业务代码 → 「日常同步」
3. **显式重建** / 初始化末尾用户同意重建 → 读 [rebuild-prompt.md](rebuild-prompt.md) → 「重建流程」

---

## 初始化流程

### 1. 探测

检查是否存在 `docs/`、`docs/intent|spec|adr`（及同义路径）。阅读已有文件用途，判断是否与本工作流语义冲突（例如 `docs/spec` 实际是 API 生成物或其它含义）。

### 2. 冲突处理

若命名或用途**明显冲突**：

- **停手**，说明冲突点
- 给出固定三选项，等用户选择后再继续：
  1. 沿用现有目录并映射工作流（在总索引记录映射）
  2. 改用兼容子路径 `docs/agent/{intent,spec,adr}`
  3. 由用户指定路径
- **绝不**静默覆盖或删除已有文件
- 冲突未解决前：**不**提示重建、**不**写业务代码

### 3. 缺啥补啥

无冲突或路径已选定后，仅新增缺失项：

1. 创建缺失目录
2. 缺失总索引 → 从 [templates/docs-index.md](templates/docs-index.md) 创建（填入实际根路径）
3. 各子目录缺失索引 → 从对应 `*-index.md` 创建（遵守 README/index 等价规则）
4. 若 `adr` 下无 `_template.md` → 复制 [templates/adr-template.md](templates/adr-template.md) 为 `{adr根}/_template.md`
5. **不要**往 intent/spec 塞假业务内容

### 4. 判定启发式

**有实质代码**（须满足其一）：

- 存在应用/库源码目录：`src/`、`app/`、`lib/`、`pkg/`、`cmd/` 等且内有源文件
- 或存在构建清单（如 `package.json`、`pyproject.toml`、`go.mod`、`Cargo.toml`）且仓库内有多个源文件

仅 README / 空仓 / 只有配置骨架 → **不算**有实质代码。

**intent/spec 几乎为空：**

- 对应目录中，除 `index.md`、`README.md`（作索引）、`_template.md`、`.gitkeep` 外，**没有**其它 `.md`

### 5. 可选重建提示

**仅当同时满足：** 有实质代码 + intent 与 spec 都几乎为空。

以下情况**不提示：** 空仓、已有业务文档、用户只要初始化目录、冲突未解决。

满足时：

1. 先读 [rebuild-prompt.md](rebuild-prompt.md)，用白话向用户说明「重建」含义
2. 再询问是否进行；**默认倾向否**
3. 用户明确同意后才进入重建流程

### 6. 询问写入 AGENTS.md 指针

初始化（路径已选定、目录已补齐）结束后：

1. 用白话说明：在仓库根放一小段「必读文档」指针，可在跨会话提醒 Agent 先读 docs、改行为要同步；个人 Skill 不能保证每轮都被加载
2. 询问是否写入
3. **同意：**
   - 无 `AGENTS.md` → 新建短文（见下方片段）
   - 已有 → **仅追加或补全「必读文档」小节**，不覆盖、不改写其余内容
4. **拒绝：** 跳过
5. 指针必须指向**实际文档根**（含映射路径），并简述三类同步规则

#### AGENTS.md 片段（按实际路径替换）

```markdown
## 必读文档

| 需求 | 文档 |
|------|------|
| 产品意图 | docs/intent/ |
| 行为规格 | docs/spec/ |
| 架构决策 | docs/adr/ |

改用户可感知行为 → 同步 spec；改产品意图/范围 → 同步 intent；架构/技术取舍 → 新增或更新 ADR。
纯样式/文案/重构且行为不变可不写文档；若已有 spec 写到相关细节则顺手改。
意图不清时先澄清再落文档，禁止先写代码再补文档。
```

---

## 日常同步

### 先读文档

改动前阅读相关 `intent` / `spec` / `adr`（以总索引中的根路径为准）。不要凭聊天记忆猜意图。

### 意图不清

1. 若可用 `interview-me` 则优先；否则对话内等价流程：一问一答、附带猜测、复述 Outcome/User/Why now/Success/Constraint/Out of scope，取得明确 yes
2. 确认后再落 `docs/intent`（可用 [templates/intent-template.md](templates/intent-template.md)）
3. 必要时再写/改 `docs/spec`（可用 [templates/spec-template.md](templates/spec-template.md)）
4. **然后才改代码**

### 三类强制同步

| 变更 | 文档 |
|------|------|
| 用户可感知行为 | `{spec根}/` 新建或更新 |
| 产品意图/范围 | `{intent根}/` 新建或更新 |
| 架构/技术取舍 | `{adr根}/` 新增或更新（见 ADR 惯例） |

纯样式/文案/重构且行为不变 → 可不写；若已有 spec 覆盖相关细节 → 顺手改掉。

行为或决策变更时更新对应文档；不要只改代码不留痕迹。

### ADR 惯例

- 文件名：`NNN-slug.md`（三位编号，追加，不复用）
- **不删**旧 ADR；变更时写新 ADR，旧篇 Status 改为 `Superseded by ADR-XXX`
- 更新 `adr` 索引表（`index.md` 或等价 `README.md`）追加一行
- 新篇可从 `{adr根}/_template.md` 复制

---

## 重建流程

完整话术与标记规范见 [rebuild-prompt.md](rebuild-prompt.md)。要点：

1. **先列候选模块/功能面清单**，让用户选范围；禁止对巨型仓库一次倾倒全量文档
2. 在**对话中**产出带「推测」标记的草稿；确认前**不**写入正式 intent/spec/adr
3. 用户明确要求临时落盘时，才写入 `docs/_drafts/`（可提示加入 `.gitignore`）；确认后迁入正式路径并删除草稿
4. 用户确认后去掉推测标记，再写入对应正式路径并更新索引
5. 禁止把未确认推测写成 Confirmed intent

---

## 明确不做（v1）

- CI 文档漂移检查、文档站、多语言 docs
- 自动把推测稿写成已确认事实
- 静默覆盖/删除已有文档
- 绑定某一业务仓库的专用约定
