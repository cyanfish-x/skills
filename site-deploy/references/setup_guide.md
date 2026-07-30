# site-deploy 安装与配置指南

## 1. 安装 rclone（agent 代装时按此执行）

检测：`rclone version` 失败即视为未安装。先征询用户；同意后再装。

### Windows

1. 优先：

```bash
winget install --id Rclone.Rclone -e --accept-package-agreements --accept-source-agreements
```

2. 无 winget 时：

```bash
choco install rclone -y
```

3. 再不行：从 https://rclone.org/downloads/ 下载 zip，解压后把目录加入 PATH，或在当前会话：

```bash
export PATH="/c/path/to/rclone:$PATH"   # Git Bash 示例
```

### macOS

```bash
brew install rclone
```

### Linux

优先发行版包（如 `sudo apt install rclone` / `sudo dnf install rclone`）。否则：

```bash
curl https://rclone.org/install.sh | sudo bash
```

执行前告知用户需要 sudo。

装完立刻 `rclone version` 复检。官方文档：https://rclone.org/install/

## 2. 配置 rclone remote

交互配置由**用户自己**完成（agent 不代填密钥）：

```bash
rclone config
```

记下 remote 名称（如 `my-site`），写入项目 `actions/.env` 的 `RCLONE_REMOTE`。

验证：

```bash
rclone listremotes
```

## 3. 项目 actions/.env

1. 若无 `actions/`，创建目录。
2. 将本目录旁的 `config_template.env` 复制为项目内 `actions/.env`。
3. 填写：

| 变量 | 必填 | 说明 |
|------|------|------|
| `RCLONE_REMOTE` | 是 | rclone remote 名，可带或不带末尾 `:` |
| `LOCAL_DIR` | 是 | 本地构建产物目录 |
| `REMOTE_DIR` | 是 | 远端目录路径（相对 remote 根） |
| `RCLONE_TRANSFERS` | 否 | 默认 8 |
| `RCLONE_CHECKERS` | 否 | 默认 16 |
| `CDN_SECRET_ID` / `CDN_SECRET_KEY` | CDN 时 | 腾讯云 API 密钥 |
| `CDN_FLUSH_PATHS` | CDN 时 | 逗号分隔的刷新 URL/路径 |
| `CDN_REGION` | 否 | 默认 `ap-chengdu` |

**安全**：`.env` 加入 `.gitignore`；不要把密钥贴进聊天或 commit。

## 4. skill 脚本依赖

在 skill 的 `scripts/` 目录执行一次：

```bash
npm install
```

不要求目标业务项目安装腾讯云 SDK。

## 5. 常用命令

在仓库根（或对 `--cwd` 传入仓库根）：

```bash
node <skill>/scripts/deploy.js --cwd .
node <skill>/scripts/deploy.js --cwd . --skip-cdn
node <skill>/scripts/refresh-cdn.js --cwd .
```

`--env` 可指向非默认的 env 文件（默认 `<cwd>/actions/.env`）。
