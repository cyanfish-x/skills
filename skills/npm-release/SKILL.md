---
name: npm-release
description: >-
  Generic npm package release assistant for any Node library/app repo. Discovers
  package manager and project release scripts (or falls back to a portable
  prepare → user-manual-publish → finish flow), bumps semver, optionally curates
  CHANGELOG highlights, creates annotated tags, then waits for the user to run
  publish (browser/OTP), and finally pushes tags / GitHub Release. Use when the
  user says 发版, 发布新版本, npm publish, release, cut a release, bump
  patch/minor/major, or when package.json was bumped but not actually published.
  Not for site/rclone deploy (use site-deploy) or Tellux-only internals beyond
  the shared workflow.
---

# npm-release（通用 npm 包发版助手）

把当前工作区里的 npm 包打成新版本：准备 → **用户本机手动 publish** → 收尾。  
从 tellux 发版流程抽出的**通用编排**；不绑定某个仓库的 `actions/`，有项目脚本就用，没有就走本 skill 的便携步骤。

与 `site-deploy` 分工：本 skill 只做 **npm 发包 + tag/Release**；站点 rclone/CDN 用 `site-deploy`。

## 三段式（硬性）

| 阶段 | 谁执行 | 做什么 |
|------|--------|--------|
| **准备** | 助手 | 校验 / 升版本 / changelog（可选）/ commit / **annotated** tag |
| **publish** | **仅用户本机** | `pnpm`/`npm`/`yarn` publish（浏览器 2FA / OTP） |
| **收尾** | 助手（用户确认已发布后） | `git push --follow-tags` + 可选 GitHub Release |

助手**禁止**执行任何 `npm publish` / `pnpm publish` / `yarn npm publish`。非交互环境过不了 npm 验证。

## 何时使用

- 「发版」「发布新版本」「release」「publish 这个包」「cut a release」
- 升 patch / minor / major
- 「上次只改了 package.json 版本、没真正发到 npm」→ 走「半途恢复」

不要用本 skill：前端站点部署、只建 GitHub Release 不发 npm（除非用户明确只要补 Release）、私有 registry 发版（需先改规则，默认只认 `https://registry.npmjs.org/`）。

## 前置探测（每次发版先跑，用本机证据说话）

在仓库根目录核实并记下：

```bash
git branch --show-current
git status --porcelain
node -p "const p=require('./package.json'); JSON.stringify({name:p.name,version:p.version,scripts:Object.keys(p.scripts||{}),packageManager:p.packageManager||null,publishConfig:p.publishConfig||null})"
git describe --tags --abbrev=0 2>/dev/null || echo '(no tags)'
# 包管理器：有 pnpm-lock.yaml → pnpm；yarn.lock → yarn；否则 npm。若同时有 lock，以用户/项目惯用为准并问一句。
ls pnpm-lock.yaml yarn.lock package-lock.json 2>/dev/null
test -f actions/release.js && echo 'has-project-release-scripts'
test -f CHANGELOG.md && echo 'has-changelog'
npm view <packageName> version --registry https://registry.npmjs.org/ 2>/dev/null || true
gh auth status 2>&1 | head -5
```

**停下并告知用户**（满足任一条就先别发）：

1. 工作区不干净（有未提交改动）——让用户先 commit/stash；**不要**替用户提交无关改动。
2. 分支不符合项目约定（有 `dev` 发版惯例就要求在 `dev`；否则用用户指定分支，并口头确认）。
3. 线上 npm 已有目标版本，且用户没说要补 tag/Release——避免重复 publish。

包管理器选择：

- 项目用 **pnpm** 且 `node_modules` 为符号链接布局 → publish/pack **必须 pnpm**（npm arborist 易崩）。
- 纯 npm / yarn 项目用对应工具；命令里一律带 `--registry https://registry.npmjs.org/`（本机常默认 npmmirror）。

## 主流程

### 1. 确认版本类型（不可跳过确认）

从自上次 tag（或自认为已发版本）以来的 commit 建议：

- 有 `feat:` → 建议 **minor**
- 仅 `fix:` / `refactor:` / `perf:` → 建议 **patch**
- 有 `!:` / BREAKING → 建议 **major**

**发版不可逆，必须用户确认 patch/minor/major（或明确目标版本号）后再继续。**

半途场景：`package.json` 已是目标版本、npm 尚未有 → **不要再 bump**，只补 build/tag/publish/收尾（见文末）。

### 2. 发版摘要（有 CHANGELOG 时）

若存在 `CHANGELOG.md` 且含 `## [Unreleased]`：

```bash
git describe --tags --abbrev=0
git log <lastTag>..HEAD --pretty=format:"%h %s"
```

归纳 **3–5 条主题级亮点**写入 `## [Unreleased]` 下（给用户确认后再 commit）：

- 可用散文或 `-` bullet；**不要用 `###` 标题**（项目若有 `generate-changelog.js`，`###` 会被当成「全手写」而不追加自动清单）。
- 扫 commit 时包含 merge / 无前缀说明，不要只看 `feat:`/`fix:`。
- 提交：`docs(changelog): 补充发版摘要`，让工作区回到干净。

无 CHANGELOG 时：跳过本步；收尾 GitHub Release notes 可用确认过的摘要文本或 `git log` 精简列表。

### 3. 发版准备（到 annotated tag 为止）

#### 路径 A — 项目自带脚本（优先）

若存在 `actions/release.js`（或 `package.json` 脚本明确指向同等流程）：

```bash
node actions/release.js <patch|minor|major>
```

按其输出停止；**不要**代跑 publish / push。

#### 路径 B — 便携准备（无项目脚本时，如 cesium2s）

1. **门禁**：按 `package.json` scripts 尽量跑通（存在则执行，失败则停）：
   - 优先 `release:check`；否则依次尝试合理子集：`typecheck`/`type-check`、`test`/`test:run`、**必跑** `build`（历史教训：未 build 就 publish）。
2. **升版本**（半途已对齐版本则跳过）：

   ```bash
   npm version <patch|minor|major> --no-git-tag-version
   ```

3. **Changelog 自动段**（可选）：若有 `actions/generate-changelog.js`，执行  
   `node actions/generate-changelog.js --version <新版本>`。
4. **提交 + annotated tag**：

   ```bash
   git add package.json CHANGELOG.md   # 仅已改文件
   git commit -m "chore(release): 发布 v<新版本>"
   git tag -a "v<新版本>" -m "发布 v<新版本>"
   ```

   **必须** `git tag -a`；轻量 tag 不会被 `git push --follow-tags` 推送。

准备结束后**只打印**用户手动 publish 命令，然后等待。

### 4. 用户手动 publish

按探测到的包管理器给出**一条**完整命令（示例）：

```bash
# pnpm
pnpm publish --no-git-checks --registry https://registry.npmjs.org/

# npm（无 pnpm 时）
npm publish --registry https://registry.npmjs.org/

# yarn berry
yarn npm publish --registry https://registry.npmjs.org/
```

说明：

- 必须显式 `--registry https://registry.npmjs.org/`。
- pnpm 在 tag 尚未 push 时需要 `--no-git-checks`。
- 在用户本机终端执行，以便浏览器/OTP。

等待用户回复「已发布」或「继续」。可用只读核对：

```bash
npm view <packageName> version --registry https://registry.npmjs.org/
```

### 5. 收尾

确认 npm 已是新版本后：

#### 路径 A

```bash
node actions/release-finish.js <新版本>
```

#### 路径 B

```bash
git push --follow-tags
# 有 CHANGELOG 且有 actions/github-release.js：
node actions/github-release.js <新版本>
# 否则：
gh release create "v<新版本>" --title "v<新版本>" --notes-file <notes.md>
# 或 --notes "…"；已有 Release 则 gh release edit
```

`gh` 未登录时：仍完成 push；告警并给出补建命令，不把 npm 成功打成失败。

### 6. 确认

```bash
npm view <packageName> version --registry https://registry.npmjs.org/
gh release view v<新版本>   # 若建了 Release
```

## 半途恢复

| 状态 | 做法 |
|------|------|
| 版本已 bump，无 tag / 未 publish | **勿再 bump**；补 build → annotated tag → 用户 publish → 收尾 |
| 已有 `chore(release)` + tag，未 publish | 只让用户跑 publish |
| npm 已发布，未 push/Release | 只跑收尾 |
| 误跑第二遍准备脚本 | 会再次升版本——发现后立即停下与用户对齐 |

## 补建历史 GitHub Release

不重发 npm：确保远端有 tag，再 `gh release create` / 项目 `github-release.js`；旧版本加 `--no-latest`（或等价），避免抢 Latest 徽章。

## 关键坑点（从 tellux / cesium2s 实战抽出）

- **publish 禁止助手代跑**。
- **registry 写死 npmjs.org**，防 npmmirror 鉴权失败。
- **先 build 再 publish**（cesium2s 曾因未 build 发失败）。
- **annotated tag**，否则 `--follow-tags` 推不上去。
- **pnpm 项目不要用 npm pack/publish**。
- Conventional Commits 利于自动 changelog；写「版本重点」仍要读 merge/无前缀提交。
- 默认分支/发版分支因仓库而异：先探测，再套「必须在 dev」等项目惯例。

## 与项目专用 skill 的关系

- **tellux** 仓库内 `.agents/skills/release` 仍可保留：写死 pnpm、`release:check`、changelog 细则。通用流程以本 skill 为准；tellux 脚本 = 路径 A 的实现。
- 新仓库优先直接用本 skill（路径 B），不必先抄一整份 `actions/`。
