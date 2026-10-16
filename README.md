# skills

个人 AI agent skill 集合，配合 ZCode、Claude Code 等遵循 `~/.agents/skills/`
目录约定的 agent 使用。本机通过 junction 把仓库里的 skill 目录链接到
`~/.agents/skills/` 下完成启用，由 `scripts/` 下的脚本统一维护。

## 目录结构

```
skills/            自研 skill（每个子目录一个，含 SKILL.md）
agent-skills/      上游 addyosmani/agent-skills 的 git 子模块（只存指针，不复制内容）
agent-skills.conf  从上游启用的 skill 清单
scripts/           junction 同步等维护脚本
agents/            子 agent 定义
design/            living-context 的版本设计笔记（非 skill）
```

## 自研 skill


| Skill                                   | 说明                                                                      |
| --------------------------------------- | ----------------------------------------------------------------------- |
| [cyanfish-write](skills/cyanfish-write) | 青花鱼博客（Hexo）写作风格指南：口语化、类比、结构规范，含语句通顺与去 AI 味自查                            |
| [frontend-debug](skills/frontend-debug) | 前端浏览器 bug 的假设驱动调试：注入埋点 → 用户复现 → 读日志验证/证伪猜想，迭代定位根因                       |
| [image-compress](skills/image-compress) | 用 sharp 压缩图片；`--max-bytes` 时自动降质量逼近目标体积，格式转换与缩放仅在明确要求时进行                |
| [living-context](skills/living-context) | 项目知识的检索、核验与局部维护：复用非显然约束与历史决策，按需沉淀高价值根因与结论                               |
| [npm-release](skills/npm-release)       | 通用 npm 发版助手：识别包管理器与发版脚本，bump semver、整理 CHANGELOG、打 tag、建 GitHub Release |
| [site-deploy](skills/site-deploy)       | 前端站点部署：构建产物经 rclone 增量同步到服务器，可选腾讯云 CDN 路径刷新                             |
| [tellux-use](skills/tellux-use)         | Tellux 0.2 API 参考（已过期，0.3 起请改用 tellux 仓库内的 skill）                       |
| [weekly-report](skills/weekly-report)   | 按本机 git 账户上周（或指定区间）的提交生成中文工作周报，按功能模块分组润色                                |




## 引用上游 skill（agent-skills 子模块）

[agent-skills](agent-skills) 是指向 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)
的 git 子模块，仓库里只保存一个 commit 指针。实际启用哪些 skill 由
[agent-skills.conf](agent-skills.conf) 决定，每行一个目录名，`#` 开头为注释：

```conf
api-and-interface-design
code-review-and-quality
code-simplification
interview-me
```

运行 [scripts/link-agent-skills.sh](scripts/link-agent-skills.sh) 把清单内的 skill
以 junction 链接到 `~/.agents/skills/`，不在清单里的上游 skill 不会被启用。

## 常用操作

```bash
# 新机器初始化
git clone --recurse-submodules https://github.com/cyanfish-x/skills.git
./scripts/link-local-skills.sh     # 启用全部自研 skill
./scripts/link-agent-skills.sh     # 启用清单内的上游 skill

# 新增/删除自研 skill：在 skills/ 下增删目录后同步
./scripts/link-local-skills.sh [--check]

# 增减启用的上游 skill：编辑 agent-skills.conf 后同步
./scripts/link-agent-skills.sh [--check]

# 跟进上游更新（已建的 junction 无需变动）
git submodule update --remote agent-skills
git add agent-skills && git commit
```

两个脚本面向 Windows（Git Bash 调 PowerShell 创建 junction），重复执行幂等；
只增删指向本仓库的 junction，其他链接和实体目录一律不动。自研 skill 修改后
直接 commit 即可，junction 指向仓库目录，改动即时生效。

## 子 agent（agents/）

[agents/](agents) 每个文件定义一个子 agent，格式与 ZCode 插件内置 agent 一致：
frontmatter 含 `name`、`description`（主模型靠它判断何时分派）、`model`、
`thoughtLevel`、`tools`，正文为系统提示词。[fast-worker](agents/fast-worker.md)
是通用模板——把机械性任务（查找/读取/按指令改文件、跑命令汇总输出）交给轻量
快速模型执行，接入时在 frontmatter 填入本机可用的模型 ID 即可，不填则继承主会话模型。

用户级接入路径为 `~/.zcode/agents/`。junction 只能链接目录、无法链接单个文件，
所以本目录内容需手动复制过去；仓库侧是未绑定模型的模板，`~/.zcode/agents/`
下是绑定模型的实例，改模板后记得同步实例。

## License

自研部分见 [MIT License](LICENSE)。`agent-skills/` 子模块内容归上游仓库所有，
遵循其自身的分发许可。