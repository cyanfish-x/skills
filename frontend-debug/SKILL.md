---
name: frontend-debug
description: 前端浏览器 bug 的假设驱动调试。用户描述问题（界面不显示/消失、数据不对、交互不响应、UI 闪烁/滚动错乱、行为不符合预期等）时，读取相关代码提出多个可证伪猜想，自动生成埋点代码注入可疑位置（fetch 上报到本地服务），让用户复现问题后读取落盘日志验证/证伪猜想，迭代定位根因。在用户说"调试前端""排查前端 bug""界面消失了""为什么没生效""这个 bug 怎么回事"等时使用。仅覆盖浏览器端，不支持 Node 后端。
---

# Frontend Debug（前端假设驱动调试）

## 用途

借鉴 Cursor debug 模式，把"反复截图问用户、靠图像识别读 console、来回猜测"的低效调试，升级为**结构化的假设驱动 + 埋点取证**：

1. 先把模糊现象拆成**多个互斥、可证伪**的猜想（H1/H2/H3）
2. 每个猜想配一个**埋点**，采集能区分该猜想的数据
3. 埋点通过 `fetch` 上报到本地日志服务，落盘成文件
4. 用户复现一次问题，agent 直接读日志文件用**数值**验证/证伪猜想
5. 迭代直到锁定根因，最后清理所有埋点

核心优势：日志是**结构化数值/状态**而非截图，agent 可精确判断，避免人工描述和图像识别的误差。

## 工作流程

### 第 1 步：读代码 + 提猜想

读用户指出的相关代码（或主动搜索定位）。把"现象"翻译成**互斥、可证伪**的猜想，每条写明：**如果是这个原因，日志里会看到什么；如果不是，会看到什么**。

举例（现象："红线跑两轮后消失"）：
- H1 DOM 被清除 → 日志 `document.contains(line)` 出现 false
- H2 位置算错 → 日志 `visibleLeft` 超出 `[0, clientWidth]` 或为负
- H3 滚动不同步 → 日志 `scrollLeft` 设置后读回的值不一致

详见 `references/hypothesis_guide.md`。

### 第 2 步：生成并注入埋点

对每个猜想调用脚本生成埋点代码（路径相对本 skill 目录）：

```bash
python scripts/inject_probe.py --probe-id H1 --location "setPlaybackDate" \
  --message "cursor position" --fields "absoluteLeft,scrollLeft,visibleLeft" --port 7559
```

stdout 输出带 `// #region probe H1 ... // #endregion` 标记的 JS 片段。**用 Edit 工具把它注入到代码的可疑位置**（关键分支、循环、事件回调内）。

**埋点位置原则**：只埋能区分猜想的关键点，不要满屏埋点。一条猜想 1 个埋点即可。

### 第 3 步：启动日志服务

**必须**在**目标项目根目录**下用后台 Bash 启动服务（日志写到该目录的 `.frontend-debug/logs.jsonl`）：

```bash
# 后台启动（--reset 清空旧日志，run_in_background: true）
node <skill目录>/scripts/log_server.js --port 7559 --reset
```

读 stdout 的 JSON（含 `url`/`port`/`logFile`/`pid`），记下 `pid` 备停服用。把 `url`（如 `http://127.0.0.1:7559`）和埋点所在端口告诉用户。

> 端口冲突会自动 +1 重试，以实际 stdout 的 `port` 为准。生成埋点时如端口非 7559，传对应的 `--port`。

### 第 4 步：请用户复现 → 读日志验证

请用户在浏览器复现问题（操作触发埋点）。然后 agent **直接读日志文件**验证，不需要问用户、不需要截图：

```bash
# 读全部
cat .frontend-debug/logs.jsonl
# 按 probe_id 过滤
grep '"probe_id": "H1"' .frontend-debug/logs.jsonl
```

每行是一条 JSON：`{ts, probe_id, location, message, data, session_id}`。用 `data` 里的数值对照第 1 步的预期，判定每个猜想证实/证伪。

### 第 5 步：迭代或定位

- 全部证伪 → 缩小范围或提新猜想，回到第 2 步补埋点（服务不用重启）
- 某猜想证实 → 锁定根因，修代码
- 修复后 → **清理所有埋点**并停止服务：

```bash
# 清理某文件的全部埋点
python scripts/inject_probe.py --clean src/pages/xxx/index.vue
# 仅清指定 id
python scripts/inject_probe.py --clean src/pages/xxx/index.vue --probe-id H1

# 停止日志服务（用第 3 步记下的 pid）
kill <pid>
```

## 埋点原则

1. **catch 静默**：埋点代码必须 `.catch(() => {})`，服务没开也不能影响业务。
2. **region 标记**：用 `// #region probe <id>` / `// #endregion` 包裹，便于批量清理，绝不遗留。
3. **调完即清**：定位并修复后，必须清理所有埋点 + 停服务。不要把埋点提交进 git。
4. **采集最小集**：只采能区分猜想的字段；避免采集大对象/敏感数据。
5. **时序问题用 RAF 复查**：异步/重渲染场景，在埋点里再用 `requestAnimationFrame` 采一帧（见 `references/probe_patterns.md`）。

## 脚本依赖

- `node`（运行 log_server.js，仅用内置模块，零依赖）
- `python3`（运行 inject_probe.py，仅用标准库，零依赖）
- 两个脚本都**无需安装任何第三方包**。

## 边界

- 仅浏览器端调试。Node/后端日志请用 console/文件直接写，不走本 skill。
- 埋点是临时调试代码，不替代正式日志/监控。
