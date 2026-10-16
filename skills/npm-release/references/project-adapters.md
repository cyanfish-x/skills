# 项目适配速查

发版前用本表决定走 **路径 A（项目脚本）** 还是 **路径 B（便携步骤）**。

## 探测信号

| 信号 | 含义 |
|------|------|
| `actions/release.js` + `actions/release-finish.js` | 路径 A（tellux 同类） |
| `package.json` → `scripts.release:check` | 准备阶段优先跑它 |
| `CHANGELOG.md` + `## [Unreleased]` | 先写摘要再发版 |
| `actions/generate-changelog.js` | bump 后可自动追加分类清单 |
| `actions/github-release.js` | 收尾用它建/更 Release |
| 仅有 `build`，无 release 脚本 | 路径 B（如 cesium2s） |
| `pnpm-lock.yaml` | publish 用 pnpm |
| `publishConfig.registry` | 打印命令时仍强制 npmjs.org，除非用户明确要其它 registry |

## 路径选择

```
有 actions/release.js？
  ├─ 是 → 路径 A：node actions/release.js <type>
  └─ 否 → 路径 B：build 门禁 → npm version --no-git-tag-version
                    → commit + git tag -a → 用户 publish → push --follow-tags
```

## 半途（版本号已改、npm 未发）

1. `node -p "require('./package.json').version"` 与  
   `npm view <name> version --registry https://registry.npmjs.org/` 对比。
2. 本地已超前且 npm 无此版本 → **禁止再次 bump**。
3. 确认 `dist`/build 产物新鲜 → 缺 tag 则补 annotated tag → 用户 publish → 收尾。
