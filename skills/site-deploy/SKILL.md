---
name: site-deploy
description: 通用前端站点部署。构建产物经 rclone 增量同步到服务器，可选腾讯云 CDN 路径刷新。不绑定特定项目：读取工作区 actions/.env，自动检测/征询安装 rclone。在用户说"部署""deploy""同步到服务器""rclone 上传""刷新 CDN""上线站点"等时使用。不含 npm 发版、GitHub Pages、SSL 证书更新。
---

# Site Deploy（站点部署）

## 用途

这是一个**个人通用 skill**：把当前工作区的前端构建产物用 **rclone sync** 推到远端，并可选刷新 **腾讯云 CDN**。配置放在项目的 `actions/.env`，脚本在本 skill 的 `scripts/` 下，切换仓库即可用。

## 何时使用

- 「部署」「deploy」「同步到服务器」「rclone 上传」「上线」
- 「刷新 CDN」「purge CDN」「清缓存」
- 用户明确要走 rclone + 腾讯云 CDN 链路时

不要用本 skill：npm/pnpm publish、GitHub Pages、`sslUpdate`、与 rclone 无关的容器/K8s 发布。

## 工作流程

### 1. 确认目标

| 目标 | 动作 |
|------|------|
| 整站部署 | 构建（可跳过）→ `scripts/deploy.js`（sync + 可选 CDN） |
| 只刷 CDN | `scripts/refresh-cdn.js` |
| 只要上传已有产物 | 跳过构建，直接 `deploy.js` |

用户没说清时先问一句。

### 2. rclone 检测与安装

1. 执行 `rclone version`。命令不存在或非 0 → 判定未安装。
2. **先问后装**：提示「本机未检测到 rclone，是否由我帮你安装？」  
   - 不同意 → 中止，并给出官方文档：https://rclone.org/install/  
   - 同意 → 按 OS 非交互安装（见 `references/setup_guide.md`），装完再跑 `rclone version` 复检。
3. PATH 未刷新时，提示刷新终端或给出当前会话临时 PATH，确认可用后再继续。
4. **只装二进制，不代跑 `rclone config`**。

### 3. 其余前置检查

- `rclone listremotes`：确认 `RCLONE_REMOTE` 对应 remote 存在；不存在则引导用户自行 `rclone config`（**不代填密钥**）。
- 确认项目根下存在 `actions/.env`（可用 `--env` 指定其它路径）。  
  - **禁止**把 `.env` 全文或 `CDN_SECRET_*` 读进对话 / 写进 commit。  
  - 缺文件：从 `references/config_template.env` 复制到 `actions/.env`，让用户自行填写后再继续。
- 检查 `.env` 是否具备键名（只查键是否存在，不打印值）：`LOCAL_DIR`、`REMOTE_DIR`、`RCLONE_REMOTE`；CDN 三项可选。
- 脏工作区可部署，但口头提醒可能把未完成改动上线。

### 4. 构建（整站部署时）

在仓库根目录：

1. 读 `package.json` 的 `scripts`。
2. 若用户未要求跳过构建：优先 `build-only`，否则 `build`。用项目包管理器执行（`pnpm` / `npm` / `yarn`）。
3. Windows / pnpm：若项目自带部署脚本，用 `pnpm run deploy` / `npm run deploy`，**不要**写 `pnpm deploy`（pnpm 内置子命令）。
4. **默认推荐**：本 skill 的「自检构建 + skill 脚本」，不强行调用项目内可能绑死路径的 `actions/deploy.js`，除非用户明确要求。

### 5. 执行脚本

脚本路径相对本 skill 目录。首次使用先在 `scripts/` 下执行一次 `npm install`。

```bash
# 整站：同步 + 可选 CDN（cwd = 仓库根）
node scripts/deploy.js --cwd <repoRoot>

# 跳过 CDN
node scripts/deploy.js --cwd <repoRoot> --skip-cdn

# 指定 env 文件
node scripts/deploy.js --cwd <repoRoot> --env <path-to-.env>

# 仅刷新 CDN（缺配置或失败则非 0 退出）
node scripts/refresh-cdn.js --cwd <repoRoot>
```

### 6. 成功标志

- 部署：日志出现 `🎉 部署全流程结束！`。若警告「跳过 CDN 刷新」，同步仍成功；用户要刷 CDN 时再补齐配置后跑 `refresh-cdn.js`。
- 部署流程里 CDN API 失败默认只打错误日志，**不**把整次部署标失败（与历史行为一致）。
- 单独 `refresh-cdn.js` 失败则退出码非 0。

## 安全边界

- 不把 `CDN_SECRET_*`、rclone remote 凭据读进对话。
- 可代装 rclone；不可代跑交互式 `rclone config`。
- 不提交 `actions/.env`。

## 依赖

- 本机：`rclone`（可按本 skill 流程安装）、Node.js
- skill 脚本：`scripts/package.json` 内的 `dotenv`、`tencentcloud-sdk-nodejs-cdn`
- 项目：`actions/.env`（见 `references/config_template.env`）
