# 埋点模式参考

按问题类型选择采集什么数据。原则：**能区分猜想的最小数据集**。下面给出常见前端 bug 的埋点模板，调用 `inject_probe.py` 生成后注入。

## 1. UI 不显示 / 消失 / 闪烁

核心怀疑：DOM 被移除、尺寸塌缩、被遮挡、定位跑出视口。

采集字段（注入到更新该元素的逻辑末尾）：
- `exists`: `document.contains(el)` —— DOM 是否还在文档里
- `w`, `h`: `el.getBoundingClientRect()` 的 width/height —— 是否塌缩为 0
- `x`, `y`: rect 的 x/y —— 是否跑出视口
- `parentH`: `el.parentElement && el.parentElement.clientHeight` —— 父容器是否塌缩（height:100% 依赖它）

判断：
- `exists=false` → DOM 被框架重渲染清除（H:DOM被清除 成立）
- `h=0` 或 `parentH=0` → 高度塌缩
- `x/y` 超出视口 → 定位/滚动问题

## 2. 交互不响应（点击/拖拽无效）

核心怀疑：事件没绑定、handler 没触发、入参异常、提前 return。

在 handler 入口埋：
- `triggered`: `1`（常量，确认 handler 被调用）
- 入参：`event.type`、`event.clientX/Y`、业务参数
- 关键条件判断后的标志位（确认走到了哪个分支）

在绑定处埋：
- `bound`: `1`，确认 `addEventListener` / `onmousedown` 执行过

判断：handler 埋点没出现 → 事件没绑定或被拦截；出现但参数异常 → 入参问题。

## 3. 异步 / 时序 / 重渲染

核心怀疑：状态更新异步、框架重渲染清除了元素、滚动动画未完成就取值。

模式 A —— 链路追踪：在 async 各步骤前后埋点，看哪步后状态异常。
```
step1_before → step1_after → step2_before → step2_after
```

模式 B —— 下一帧复查（最常用）：当前帧设置后，用 `requestAnimationFrame` 采一帧，对比元素是否还在/位置是否变。
```js
// 当前帧
fetch(..., {body: JSON.stringify({probe_id:'H1', data:{left: el.style.left, exists: document.contains(el)}})})
requestAnimationFrame(() => {
  fetch(..., {body: JSON.stringify({probe_id:'H1-nextframe', data:{exists: document.contains(el), left: el.style.left}})})
});
```
判断：`H1-nextframe` 的 `exists=false` → 确诊被重渲染清除。

## 4. 滚动 / 定位错乱

核心怀疑：滚动条设置后未生效、滚动坐标系不一致、clamp 越界。

采集字段（注入到定位计算处）：
- `absoluteLeft`: 时间/数据换算的绝对像素位置
- `scrollLeft`: 当前滚动位置
- `actualScrollLeft`: 设置 `scroll.scrollLeft = x` 后**立即读回**的值（验证是否生效）
- `clientWidth`: 视口宽度
- `computed`: 最终算出的 `left` 值
- `maxScroll`: `scrollWidth - clientWidth`

判断：
- `actualScrollLeft !== scrollLeft` → 滚动没生效（H:滚动不同步 成立）
- `computed` 越界 → clamp 逻辑问题
- 到达 `maxScroll` 后 `scrollLeft` 不再增长 → 滚动到极限

## 5. 组件状态异常（Vue / React）

Vue 2/3：在方法/computed 里直接引用 `this.xxx` 采集。
```js
// data 值
data: { playProgressIndex: this.playProgressIndex, isAutoScroll: this.isAutoScroll }
// computed（注意避免无限递归，只采值不采 getter）
data: { ganttDataLen: this.ganttData.length }
```
React：在函数组件体内直接采 `state`/`props`。

## 6. 数据流 / 接口返回

在接口回调里埋返回值的结构特征（不要埋整个大对象）：
- `dataLen`: `data ? data.length : -1`
- `hasField`: `data && 'uid' in data[0]`
- `firstItem`: `data && data[0]` 的关键字段

判断字段名是否匹配（如后端返回 `donePrecent` 拼写）。

## 通用技巧

- **每条猜想配一个 probe_id**（H1/H2/H3），日志里按 id 过滤互不干扰。
- **批量采多个时间点**：同一 probe_id 在不同代码位置都埋，用 `location` 字段区分，日志按 ts 排序即可还原执行顺序。
- **避免采集超大对象**：只取长度/关键字段/布尔标志，不要 `JSON.stringify(this)`。
