# Living Context

## Knowledge Lifecycle for AI Coding Agents

> **一个长期由 Agent 开发的项目，知识如何产生、验证、沉淀、被复用、保持最新，并在失去价值时自然消失。**

Living Context 关注的不是“如何写更多文档”，而是**如何管理项目知识的生命周期**。

它希望解决一个长期存在于 AI 协同开发中的问题：

> 随着项目不断演进，积累下来的知识应该持续提高未来 Agent 和开发者的判断质量，而不是随着时间推移逐渐变成他们的认知负担。

文档只是知识的一种载体。

真正的目标是维护一套**高信噪比、低重建成本、始终可质疑、始终与当前项目状态相关的 Living Context**。

---

# 一、总纲领

> **Knowledge should amplify intelligence, not constrain it.**
> **知识应该放大智能，而不是束缚智能。**

Living Context 的目的不是告诉 Agent 应该怎么想，也不是把过去的设计选择固化成不可挑战的规则。

它应该为 Agent 提供那些：

- 重新获得成本高；
- 容易被误判；
- 仍然影响当前决策；
- 无法仅通过短时间阅读代码可靠恢复；

的知识。

然后让 Agent 在：

> **可靠事实、真实约束、已有经验和当前环境**

的基础上，继续独立判断。

知识可以包含真正需要遵守的约束，例如 API 兼容性、产品要求、安全边界和架构 invariant。

但知识不应该把：

> 历史选择、临时方案、旧技术限制、某次 Agent 的偏好

伪装成永恒规则。

因此，Living Context 的核心不是：

> **让 AI 少思考。**

而是：

> **让 AI 不必重复思考那些已经付出高成本解决过的问题，同时保留重新判断的能力。**

---



# 二、为什么知识会反过来降低智能

更多 Context 并不天然意味着更好的判断。

> **More context ≠ more intelligence.**

项目上下文中可能同时存在：

- 有效知识；
- 过期知识；
- 重复信息；
- 相互冲突的结论；
- 未验证推测；
- 历史实现细节；
- 已失效的限制；
- 被错误赋予权威的调研材料。

当这些内容不断累积时，Agent 必须先花费大量推理能力回答：

> 哪一篇才是现在有效的？

> 哪个限制还成立？

> 这是事实、决定，还是某次调研中的推测？

> 为什么当时这么做？

最终，项目积累的知识不再帮助智能，而开始消耗智能。

所以 Living Context 追求的不是：

> **Maximum Context**

而是：

> **Minimum Sufficient Context**

即：

> 在完成当前判断所需的前提下，只提供最少但足够的高质量知识。

---



# 三、Knowledge Lifecycle

知识不是写进 Markdown 就完成了。

一条知识应该拥有完整生命周期：

> **Discover → Verify → Distill → Route → Reuse → Refresh → Prune**

对应：

> **产生 → 验证 → 沉淀 → 路由 → 复用 → 更新 → 消失**



## Discover — 产生

知识可能来自：

- 编写代码；
- 阅读源码；
- 调试；
- 技术实验；
- 第三方库调研；
- 产品讨论；
- 架构设计；
- Bug 修复；
- 性能优化。

这一步产生的只是**候选知识**。

不是所有发现都值得长期保存。

---



## Verify — 验证

进入长期项目知识之前，需要区分它到底是什么。

例如：

- 已确认事实；
- 当前实现观察；
- 产品要求；
- 架构约束；
- 技术决策；
- 外部调研结论；
- 工程经验；
- 未确认推测。

尤其需要防止：

> **Inference → Fact**

也就是 AI 根据代码做出的推测，未经验证便进入正式文档，之后又被未来 Agent 当成确定事实。

---



## Distill — 沉淀

不要保存整个探索过程。

应该从：

- 聊天；
- 调试记录；
- 技术方案；
- 实验；
- 搜索结果；
- 临时 TODO；

中提炼真正具有长期价值的信息。

> **Preserve knowledge, not the process that produced it.**

沉淀的目标是：

> 用尽可能少的信息，保存未来重新获得成本最高的认知成果。

---



## Route — 路由

不同性质的知识应该进入不同位置。

推荐的知识模型：


| 类型             | 回答的问题          |
| -------------- | -------------- |
| `intent`       | 为什么做，目标和范围是什么  |
| `spec`         | 应该表现成什么        |
| `architecture` | 系统当前应该如何组织     |
| `decisions`    | 为什么当前这样选择      |
| `engineering`  | 有哪些难以重新获得的工程经验 |
| `research`     | 已验证过哪些外部技术事实   |


知识应该被放入正确语义空间，而不是所有 Markdown 平铺在一个 `notes/` 中。

---



## Reuse — 复用

知识存在的最终目的，是减少未来重复支付认知成本。

未来 Agent 修改某个模块时，不应该重新：

- 调查已经调查过的库；
- 争论已经认真讨论过的设计问题；
- 重新踩已经踩过的坑；
- 从大量代码中猜测产品意图。

Living Context 应该让它快速得到：

> **与当前任务真正相关的高密度上下文。**

---



## Refresh — 更新

知识不是永久正确的。

代码、需求、依赖、技术环境和设计前提都会变化。

因此 Living Context 必须允许知识被重新验证和更新。

> **Architecture is authoritative about current intended structure, but not infallible.**

Architecture 是当前设计意图的权威来源，但不是不可质疑的真理。

任何知识都可以在：

> 新证据出现、前提发生变化、项目目标改变

之后被重新评估。

---



## Prune — 消失

知识失去价值后应该消失。

> **Knowledge should have a lifecycle, not just a storage location.**

当一条知识：

- 前提已经失效；
- 已被新的高密度知识吸收；
- 已不再影响未来判断；
- 可以低成本从代码恢复；
- 只是历史过程；
- 与当前事实重复；
- 会误导未来 Agent；

就应该被删除。

> **Docs describe what still matters; Git preserves what happened.**

文档保存现在仍然重要的知识。

Git 保存过去发生过什么。

因此默认不需要为了“历史完整性”永久保留大量：

- superseded ADR；
- 已完成重构方案；
- 历史诊断报告；
- 过期 implementation plan；
- 无未来价值的 research；
- 旧 architecture。

---



# 四、什么知识值得长期保存

Living Context 不应该把代码仓库重新翻译成 Markdown。

> **Docs are curated context, not a duplicate of the codebase.**

判断一条知识是否值得长期保存，可以问：

> **未来一个能力很强、完全不了解项目历史的 Agent，能否低成本、可靠地重新获得这条信息？**

如果答案是：

> 能。

通常不需要记录。

如果答案是：

> 不能、成本较高、容易误判，或者会直接影响重要决策。

则值得保存。

因此：

> **Preserve expensive knowledge, not obvious information.**

保存昂贵知识，而不是显而易见的信息。

---



# 五、好知识的定义

一条健康的长期知识，应该尽可能让未来使用者知道六件事：

### Nature

它是什么性质。

是：

- Fact；
- Constraint；
- Decision；
- Guidance；
- Research；
- Observation；
- Inference。

不同性质的知识不应该获得相同权威。

---



### Provenance

它从哪里来。

例如：

- 用户明确决定；
- 官方文档；
- 源码；
- 实验；
- Benchmark；
- Issue；
- 当前实现；
- Agent 推测。

来源决定了未来应该如何信任它。

---



### Scope

它约束什么范围。

一条针对：

> WebGPU renderer

的知识，不应该无意中被解释成：

> 整个项目必须遵守。

知识应该具有明确作用域。

---



### Verification

它被验证到了什么程度。

例如：

> 官方文档写过。

和：

> 阅读源码确认。

和：

> 根据行为推测。

其可信度明显不同。

---



### Freshness

它现在是否仍然成立。

例如某个第三方库的问题可能只存在于：

> v1.3.0。

升级到 v2 后，它可能已经没有意义。

---



### Challengeability

> **在什么情况下应该重新评估这条知识？**

这是 Living Context 很重要的一项性质。

好的知识不是：

> 永远如此。

而是：

> 在当前这些前提下，这是最合理的判断。

当关键前提消失时，未来 Agent 应该拥有重新思考的自由。

---



# 六、为什么不能只保存结论

> **Preserve reasons and constraints, not conclusions alone.**

不要只保存结论，要保存理由和真正需要维持的约束。

一个糟糕的 Decision：

> 必须使用 A。

一个更好的 Decision：

> 当前使用 A，因为 X 和 Y。
> 系统真正需要保持的是约束 Z。
> B 曾被考虑过，但由于 Q 被放弃。
> 如果 X 不再成立，应重新评估 A。

这样未来 Agent 得到的不是：

> 一个禁止思考的答案。

而是：

> 一组能够帮助它继续推理的决策材料。

这对人类高级工程师也是一样。

一个资深开发者加入项目时，真正想知道的通常不是：

> “规范要求这样做。”

而是：

> 为什么？

比如：

> 为什么不能这样依赖？

> 为什么 API 是这种形状？

> 为什么不用另一套方案？

> 当时的限制现在还存在吗？

理解理由之后，一个优秀工程师可能发现：

> 原来的前提已经不存在了。

于是做出比历史方案更好的决定。

高智能 Agent 也应该拥有同样的自由。

---



# 七、Fact、Constraint 与 Guidance

Living Context 应避免把所有知识都写成命令。

一个很重要的区分是：

### Fact

已经确认的事实。

例如：

> 某版本 WebGPU API 在源码中具有某种行为。

---



### Constraint

当前项目真实存在、必须遵守的限制。

例如：

> Public API 不能破坏向后兼容性。

这是知识应该真正限制 Agent 的地方。

---



### Guidance

有助于判断，但不是不可违反的规则。

例如：

> 之前方案 A 的维护成本较高，因此当前更倾向 B。

未来如果前提变化，Agent 可以重新判断。

这一区分可以避免：

> 历史经验 → 被误解成强制规则。

---



# 八、不同知识源拥有不同 Authority Scope

Living Context 不定义一个：

> 所有情况下都成立的“唯一真相来源”。

不同来源回答不同的问题。

### Code

回答：

> 系统现在实际上怎么运行。

> **Code is executable state, not universal truth.**

代码是当前实现状态的直接证据，但不能证明产品本来应该如何表现。

---



### Spec

回答：

> 用户、API 或调用方应该观察到什么行为。

如果 Code 与 Spec 冲突，意味着：

> Implementation Drift

而不是自动认为 Code 或 Spec 一定正确。

---



### Architecture

回答：

> 系统当前期望如何组织。

它描述：

- 结构；
- ownership；
- responsibilities；
- boundaries；
- lifecycle；
- invariants。

---



### Decisions

回答：

> 为什么当前选择是这样。

它保存当前仍然有价值的：

- 非显然选择；
- 理由；
- 真实约束；
- 重要替代方案；
- reconsider conditions。

---



### Engineering

保存：

> 未来实现仍然有价值，但难以从代码表面重新获得的工程知识。

例如：

- 框架坑点；
- 生命周期陷阱；
- 性能限制；
- 兼容问题；
- 调试后确认的根因。

---



### Research

保存：

> 可复用的外部技术证据。

> **Research informs decisions; decisions define the project.**

Research 可以是真实、可靠、经过源码验证的事实。

但某个外部库使用 A：

> 并不意味着项目也必须使用 A。

Research 是决策材料，而不是项目选择本身。

---



# 九、Architecture 的定义

> **Architecture describes current intended structure and invariants, not historical implementation choices.**

Architecture 描述项目：

> 当前期望的系统结构、职责边界和必须维持的 invariant。

而不是记录项目过去怎么一步一步走到今天。

糟糕的 Architecture：

> 禁止 X。
> 必须 Y。
> 永远不能 Z。

它告诉 Agent：

> 不要思考。

更好的 Architecture：

> 当前系统采用 Y。
> Y 保证了 A、B、C 三个 invariant。
> 修改当前结构可以，但必须确保这些 invariant 仍然成立。

它告诉 Agent：

> **你可以重新思考实现方式，但不要无意中破坏真正重要的东西。**

这正是 Living Context 希望达到的状态。

---



# 十、Decision 应该是 Living Decision

Decision 不应该天然等同于永久历史记录。

它应该保存：

> 当前仍然成立、且未来有可能再次被讨论的重要决策。

建议一个好的 Decision 至少说明：

```text
Decision
当前选择是什么

Rationale
为什么这样选择

Constraints / Invariants
真正需要长期保持的东西是什么

Alternatives
哪些重要替代方案曾被考虑

Reconsider when
什么前提发生变化时应该重新评估当前决定
```

如果 Decision 改变：

> 更新当前 Decision。

历史由 Git 保存。

不需要默认维护：

> ADR-001 → ADR-017 → ADR-042

让未来 Agent 自己拼接最终状态。

---



# 十一、Selective Context

> **Load only relevant context.**

Living Context 不要求 Agent 每次开发前阅读所有项目文档。

这本身会制造新的认知负担。

Agent 应该：

> 根据当前任务，只读取相关的 Intent、Spec、Architecture、Decision、Engineering 和必要的 Research。

因此项目的 `docs/index.md` 更适合作为：

> **Context Router**

而不是单纯的文件目录。

目标始终是：

> **最小充分上下文。**

---



# 十二、知识冲突意味着 Drift，而不是自动选边

当出现：

```text
Code ≠ Spec
Architecture ≠ Code
Decision ≠ Architecture
Research ≠ Current assumption
```

不应该机械地规定：

> Code 永远正确。

也不应该规定：

> Docs 永远正确。

冲突本身是一条重要信号：

> **某部分知识已经发生 Drift。**

正确做法是：

> 识别冲突 → 检查证据 → 判断前提 → 更新实现或知识。

Living Context 不要求知识永远正确。

它要求：

> **知识能够被发现已经不再正确。**

---



# 十三、五个核心原则



## 1. Knowledge should amplify intelligence, not constrain it.

**知识应该放大智能，而不是束缚智能。**

知识应该帮助 Agent 判断，而不是替 Agent 判断。

---



## 2. Preserve expensive knowledge, not obvious information.

**保存昂贵知识，而不是显而易见的信息。**

优先保存未来难以低成本、可靠重建的知识。

---



## 3. Preserve reasons and constraints, not conclusions alone.

**保存理由和真实约束，而不只是结论。**

让未来 Agent 理解为什么，并知道什么时候可以重新考虑。

---



## 4. Docs describe what still matters; Git preserves what happened.

**文档保存现在仍然重要的知识，Git 保存历史。**

项目文档不是历史博物馆。

---



## 5. Distill, reuse, refresh, then prune.

**沉淀、复用、更新，并在知识失去价值时让它消失。**

知识的终点不一定是永久保存。

有价值时存在，失去价值时退出 Living Context。

---



# 十四、Living Context 最终追求的状态

理想情况下，一个第一次进入项目的高能力 Agent 不需要先进行大规模项目考古。

它应该能够快速获得：

> 我们为什么做这件事。
> 系统应该表现成什么。
> 当前系统怎样组织。
> 哪些设计已经认真思考过，以及为什么。
> 哪些约束是真正必须保持的。
> 哪些坑已经付出过代价。
> 哪些外部事实已经验证过。
> 哪些知识仍然值得相信。
> 哪些结论可以在条件变化时重新讨论。

然后：

> **把自己的推理能力留给今天真正新的问题。**

Living Context 最终不是为了管理 Markdown。

它是在管理：

> **一个长期由人类与 AI Agent 共同演化的软件项目的集体记忆。**

而 Knowledge Lifecycle 要解决的就是：

> **这些记忆应该如何产生、验证、沉淀、被复用、持续更新，并最终在不再有价值时自然消失。**

