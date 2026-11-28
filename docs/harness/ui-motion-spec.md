# ColabReel 助手界面：视觉、动效与文案硬规格

适用范围：`WorkflowBoard`、`WorkflowAgent`、`AgentPlugins`、`ProposalCard`、`ConflictBar`、`OperationCard`，以及 `Workflow.tsx` 里 `StepOutput` 的内联「AI 改写」。文案唯一来源是 [`web/src/features/workflow/agentCopy.ts`](../../web/src/features/workflow/agentCopy.ts)。

本文每一条都是硬约束。实现与本文冲突时以本文为准；本文没写到的地方，按 `app.css` 文件头的方向处理：macOS 风格创作工作台，冷蓝中性色，单一电光青 `--accent`，液态玻璃，克制。

术语：「浮窗」指助手面板 `.workflow-agent`；「启动按钮」指收起态 `.agent-launch`；「停靠」指 ≥1280px 时浮窗贴右侧、主区让出位置。

---

## 1. 视觉与 Token

### 1.1 只能用的东西

| 类别 | 允许 |
|---|---|
| 颜色 | `app.css` 里的 CSS 变量：`--bg --bg-2 --fg --fg-soft --muted --faint --line --line-strong --glass --glass-solid --glass-hi --shade --shade-2 --accent --accent-2 --accent-ink --accent-soft --ok(-soft) --warn(-soft) --bad(-soft)`；以及 `color-mix(in srgb, var(--x) N%, transparent)` |
| 阴影 | `var(--shadow)`、`var(--shadow-lg)`、`inset 0 1px 0 var(--glass-hi)`、焦点/选中环 `0 0 0 Npx var(--accent-soft)`（N ≤ 3） |
| 模糊 | `var(--blur)` |
| 圆角 | `--r-sm(10) --r(16) --r-lg(22) --r-xl(28)`、胶囊 `99px` |
| 缓动 | CSS 里用 `var(--ease)`；JS 里用 §2.1 的 `EASE` |
| 通用类 | `.glass .glass-solid .btn(.sm .ghost .primary .danger) .iconbtn(.sm .on) .tag(.ok .warn .bad .run) .warnbox .chip(.on) .chips .dot(.ok .busy .warn .bad) .badge-dot .spinner .bar(.thin .indet) .seg（经 Seg 组件）.mini-link .row .grow .tabular .mono .lbl .dim` |
| 图标 | 只用 `lucide-react`，12–17px |
| 布局用自定义属性 | 允许在 `workbench.css` 新增**非颜色**变量，目前只有 `--agent-w: 370px` |

### 1.2 禁止

1. `workbench.css` 与 7 个组件里出现裸十六进制色、`rgb()/rgba()/hsl()`、`white`/`black`/`#000` 等颜色字面量。原型里的以下写法必须删掉：
   - `.graph-refs button { background: #16202b }` → `var(--shade-2)`
   - `.graph-refs span`（白字、`rgba(0,0,0,.82)` 渐变、`text-shadow: 0 1px 3px #000`）→ 整条删除，缩略图不再叠文字
   - `.package-actions .btn.primary { background: color-mix(... #00346a) }` → 删除，直接用 `.btn.primary`
   - `.agent-launch { background: var(--fg); color: var(--bg-2) }` 反色按钮 → 按 §3.2 改为玻璃按钮
2. 新的阴影数值、多层阴影、发光（glow）、渐变描边。
3. `title` 属性做提示。唯一例外：被截断的名称可以用 `title` 放完整名称，内容只能是用户数据本身。
4. `<small>` 说明文字、副标题、括号补充说明。
5. 装饰 emoji。节点图与助手里一律用 lucide 图标；`step_catalog` 自带的 emoji 不进入这 7 个组件。
6. `!important`（`prefers-reduced-motion` 全局规则除外，那条在 `app.css` 已有）。

机检（Codex 提交前跑，必须零输出）：

```bash
rg -n '#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|\b(white|black)\b' web/src/features/workflow/workbench.css
rg -n 'box-shadow' web/src/features/workflow/workbench.css | rg -v 'var\(--shadow|var\(--glass-hi\)|0 0 0 [123]px var\(--accent-soft\)'
rg -n "title=\{?['\"\`]" web/src/features/workflow/{WorkflowBoard,WorkflowAgent,AgentPlugins,ProposalCard,ConflictBar,OperationCard}.tsx
rg -n '[一-鿿]' web/src/features/workflow/{WorkflowBoard,WorkflowAgent,AgentPlugins,ProposalCard,ConflictBar,OperationCard}.tsx | rg -v ':\s*(//|/\*|\*|\{/\*)'
```

最后一条：组件文件里除注释外不得出现中文字面量，所有用户可见中文从 `agentCopy.ts` 取。`Workflow.tsx` 里本次新增或改动的 `StepOutput` 代码同样遵守。

### 1.3 对比度

下表是在 `--glass-solid` 叠到 `--bg` 上的合成底色上，按 WCAG 相对亮度公式算出的近似值。浮窗、卡片、节点的底都按 `--glass-solid` 处理。

| Token | 浅色 | 深色 | 用法 |
|---|---|---|---|
| `--fg` | ≈15:1 | ≈14:1 | 正文、标题、回复文字、警示条内文字 |
| `--fg-soft` | ≈9:1 | ≈10:1 | 承载信息的次要文字（元信息、徽章、节点类型行） |
| `--muted` | ≈4.4:1 | ≈5.5:1 | 只用于占位符、计数、分隔符这类可省略的信息 |
| `--faint` | ≈2.9:1 | ≈3.3:1 | **不得用于文字**。只用于分隔线、装饰图标、禁用态 |
| `--accent` 作文字 | ≈3.6:1 | ≈4.4:1 | 只用于 ≥13px、字重 ≥600 的可点击文字，以及图标 |
| `--ok/--warn/--bad` 作文字 | ≈3.3–4.2:1 | ≥5.8:1 | 只出现在 `.tag` 短标签里；句子一律 `--fg`，语义色只给图标 |
| 白字 / `--accent`（`.btn.primary`） | ≈3.6:1 | 同 | 按 UI 组件 3:1 放行，字重 ≥600 |

由此产生的硬规则：

- `.warnbox` 在这些组件里一律加 `color: var(--fg)`，只有图标保持 `--warn`。
- `StepOutput` 里分镜的 `<small className="dim">{video_prompt} · {audio_notes}</small>` 改为 `--fg-soft`，否则浅色下只有约 2.9:1。
- 输入框占位符：`color: var(--muted); opacity: 1`。
- 终验以 CDP 实测为准：正文 ≥4.5:1，≥13px 且字重 ≥600 的控件文字 ≥3:1。

### 1.4 字号、间距、尺寸

| 用途 | 规格 |
|---|---|
| 浮窗标题 | 15px / 650，`letter-spacing: -.01em` |
| 空态标题 | 16px / 650 |
| 回复正文、用户气泡 | 13.5px，行高 1.6 |
| 卡片正文、提示词 diff | 13px，`line-height: 20px`（动效按 20px 行高计算折叠高度） |
| 卡片标题、元信息 | 12.5px；标题 620，元信息 450 |
| 工具徽章、节点类型行 | 11.5px / 550，最小字号，不得更小 |
| 窄屏输入框 | 16px（防 iOS 缩放） |
| 间距 | 只用 4 / 6 / 8 / 10 / 12 / 14 / 16px |
| 点击区 | 桌面 `.btn.sm` 26px、`.iconbtn.sm` 28px 可用；≤760px 时这 7 个组件里所有按钮最小 36×36px |

### 1.5 响应式布局

浮窗有四种停靠状态，写在 `data-dock` 上，取代原型的 `:not([style])` 判断：

| `data-dock` | 条件 | 位置与尺寸 |
|---|---|---|
| `right` | 视口 ≥1280px，且用户没有拖动过 | `top: calc(var(--top) + 18px + env(safe-area-inset-top, 0px))`；`right: max(16px, env(safe-area-inset-right))`；`bottom: max(10px, env(safe-area-inset-bottom))`；宽 `var(--agent-w)`。主区让出 `var(--agent-w) + 12px` |
| `float` | 761–1279px，没拖动过 | `right/bottom: max(20px, safe-area)`；宽 `var(--agent-w)`；高 `min(520px, calc(100dvh - var(--top) - 48px))`。主区不让位 |
| `free` | 任意桌面宽度，用户拖动过或点了「移到另一侧」 | `left: 0; top: 0; right: auto; bottom: auto`，位置由 `x/y` MotionValue 承载（§2.3）。主区不让位 |
| `sheet` | ≤760px | `left: 8px; right: 8px; bottom: max(8px, safe-area)`；高 `min(62dvh, 520px)`。「移到上方」后改为 `top: calc(var(--top) + 14px)`、`bottom: auto`。不可拖动 |

桌面 1440px：`.wf` 两栏为 `228px minmax(0, 1fr)`，浮窗停靠在右侧，从顶栏下沿到视口底部满高。

窄屏 390px：
- 页面不得出现横向滚动（`scrollWidth ≤ 390`）。
- 浮窗左右各 8px，宽 374px；底部卡片里按钮允许换行，换行后右对齐。
- 启动按钮 `right: 12px; bottom: max(12px, safe-area)`，高 44px。
- 节点图视口高 200px，节点不缩小，靠横向滚动查看。

### 1.6 修复拖动后右侧留白 382px

原因：原型用 `body:has(.workflow-agent) .wf { padding-right: 382px }`，浮窗拖到左边后选择器依旧命中。改为只在停靠态让位：

```css
:root { --agent-w: 370px; }
@media (min-width: 1280px) {
  body:has(.workflow-agent[data-dock='right']) .wf {
    grid-template-columns: 228px minmax(0, 1fr);
    padding-right: calc(var(--agent-w) + 12px);
  }
}
```

时序：
- 打开：浮窗挂载的同一帧让位，主区一次性重排，由浮窗入场动画带走视线。不对 `padding-right` 做过渡（逐帧重排节点图和步骤卡会掉帧）。
- 收起：退场动画期间浮窗仍在 DOM 里，`data-dock='right'` 继续生效；`onExitComplete` 后才释放让位，内容不会在浮窗还没消失时就冲进去。
- 拖动：按下拖动时保持 `right`，**松手时**才改为 `free` 并释放让位，避免拖动过程中背景内容跳动。
- 双击标题栏：先用弹簧把浮窗送回停靠位置，动画结束后再设为 `right`。
- 窗口尺寸变化：重新计算 `data-dock`，`free` 回到默认态（沿用原型行为）。

验收：1440px 下拖到左侧松手后，`getComputedStyle(.wf).paddingRight === '0px'`，右侧不留空白。

---

## 2. 动效（Motion v14）

### 2.1 统一参数：新建 `web/src/ui/motion.ts`

`Overlay.tsx` 改为从这里导入 `spring` 与 `fade`，数值不变。

```ts
import type { Transition } from 'motion/react'

/** 与 CSS var(--ease) 相同 */
export const EASE = [0.32, 0.72, 0, 1] as const

/** 面板、卡片、指示块。阻尼比约 0.93，约 190ms 稳定，无可见回弹（与 Overlay 现值一致） */
export const spring: Transition = { type: 'spring', stiffness: 420, damping: 34, mass: 0.8 }
/** 小元素：徽章、图标、状态标签。阻尼比约 1.09，无回弹，更快 */
export const springSmall: Transition = { type: 'spring', stiffness: 560, damping: 40, mass: 0.6 }
/** 高度展开/折叠。高度动画一律用补间，不用弹簧（弹簧过冲会让下方内容抖动） */
export const expand: Transition = { duration: 0.26, ease: EASE }
/** 淡入淡出 */
export const fade: Transition = { duration: 0.18, ease: EASE }
/** 内容切换 */
export const quick: Transition = { duration: 0.14, ease: EASE }
export const instant: Transition = { duration: 0 }
```

### 2.2 `useReducedMotion()` 总则

与 `Overlay.tsx` 一致：

- 入场：`initial={reduce ? false : {...}}`，直接出现在终态。
- 退场：`exit={reduce ? { opacity: 0 } : {...}}`，`transition={reduce ? instant : ...}`。
- `layoutId`、`layout`、高度展开：`transition={reduce ? instant : ...}`。
- CSS 过渡与关键帧已由 `app.css` 的全局媒体查询压到 0.01ms，不需要额外处理。
- 顺带修正 `Seg`：`layoutId` 的 `transition` 改为 `reduce ? instant : spring`。

### 2.3 浮窗：启动按钮 ↔ 面板

两者是同一个 `<AnimatePresence initial={false}>` 下的兄弟节点（key 分别为 `launch`、`panel`），交叉过渡，不用 `mode="wait"`。

**变换原点指向启动按钮。** 用 MotionValue，避免额外渲染：

```tsx
const originX = useMotionValue(1), originY = useMotionValue(1)
const launchRect = useRef<DOMRect | null>(null)

function openPanel() {
  launchRect.current = launcher.current?.getBoundingClientRect() ?? null
  setOpen(true)
}
useLayoutEffect(() => {              // 面板挂载后、首帧绘制前
  const p = panel.current?.getBoundingClientRect(), l = launchRect.current
  if (!open || !p || !l) return
  originX.set((l.left + l.width / 2 - p.left) / p.width)   // 可以超出 0–1，表示原点在面板外
  originY.set((l.top + l.height / 2 - p.top) / p.height)
}, [open])
// 收起前用当前面板位置重算一次原点，再 setOpen(false)
```

| 元素 | initial | animate | exit | transition |
|---|---|---|---|---|
| 面板（桌面三种停靠） | `{ opacity: 0, scale: 0.94 }` | `{ opacity: 1, scale: 1 }` | `{ opacity: 0, scale: 0.96 }` | `spring`；`style={{ originX, originY }}` |
| 面板（`sheet`） | `{ opacity: 0, y: 24 }` | `{ opacity: 1, y: 0 }` | `{ opacity: 0, y: 16 }` | `spring` |
| 启动按钮 | `{ opacity: 0, scale: 0.9 }` | `{ opacity: 1, scale: 1 }` | `{ opacity: 0, scale: 0.9 }` | 入场 `{ ...springSmall, delay: 0.06 }`；退场 `quick` |

- 桌面态面板入场、退场只动 `opacity` 和 `scale`，不动 `y`，因为 `free` 态的 `x/y` 被拖动占用。
- **动画期间关闭背景模糊**：`onAnimationStart` 给面板加 `data-animating`，`onAnimationComplete` 移除；CSS `.workflow-agent[data-animating] { backdrop-filter: none; -webkit-backdrop-filter: none; }`。面板底色是不透明度 0.86–0.9 的 `--glass-solid`，模糊在结束时出现几乎看不出来，但缩放过程中不再逐帧重算模糊。
- 拖动（`free`）：`x/y` 为 MotionValue，`pointermove` 里直接 `x.set()`，跟手 1:1，不加弹簧，不触发 React 渲染；松手后把位置写回 state 并钳制在视口内。
- 「移到另一侧」与双击归位：`animate(x, target, spring)`、`animate(y, target, spring)`。
- reduced motion：面板与启动按钮直接切换；「移到另一侧」瞬移。
- 焦点：打开后，精确指针设备上聚焦输入框；收起后在下一帧把焦点还给启动按钮（沿用原型）。`Esc` 收起。

### 2.4 Tab 切换

使用现有 `Seg` 组件（`ariaLabel={AGENT_COPY.agent.tabs.aria}`），共享指示块就是 `Seg` 里 `layoutId` 的玻璃块，transition 为 `spring`。这样与顶栏的分段控件是同一套视觉与手感，不再另做一种下划线样式。

Tab 内容：按 `key={tab}` 换内容，只做入场 `initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={quick}`，不做退场，避免两屏内容叠在一起。

### 2.5 对话消息与工具徽章

只给本页面新产生的内容加动画。从服务端读回的历史一律 `initial={false}`，打开浮窗时不能整屏一起飞入。

| 元素 | initial | animate | transition | 备注 |
|---|---|---|---|---|
| 用户气泡 | `{ opacity: 0, y: 8, scale: 0.98 }` | `{ opacity: 1, y: 0, scale: 1 }` | `spring` | `style={{ originX: 1, originY: 1 }}` |
| 工具徽章 | `{ opacity: 0, scale: 0.85, x: -4 }` | `{ opacity: 1, scale: 1, x: 0 }` | `{ ...springSmall, delay: i * 0.04 }` | 同一轮内按序错开，`i` 最大取 4 |
| 徽章状态图标（进行中→成功/失败） | `{ opacity: 0, scale: 0.6 }` | `{ opacity: 1, scale: 1 }` | `springSmall` | 外层 `<AnimatePresence mode="popLayout" initial={false}>`，退场 `{ opacity: 0, scale: 0.6 }` |
| 回复正文 | `{ opacity: 0, y: 4 }` | `{ opacity: 1, y: 0 }` | `fade` | |
| 「已更新」标签 | `{ opacity: 0, scale: 0.9 }` | `{ opacity: 1, scale: 1 }` | `{ ...springSmall, delay: 0.05 }` | |
| 「处理中」 | `{ opacity: 0 }` | `{ opacity: 1 }` | `{ ...fade, delay: 0.25 }` | 0.25s 内完成的请求不闪现 |
| 「回到最新」浮标 | `{ opacity: 0, y: 6 }` | `{ opacity: 1, y: 0 }` | `springSmall` | 退场 `{ opacity: 0, y: 6 }` |

滚动：新内容到来时，如果用户离底部不超过 48px，就 `scrollTo({ top, behavior: reduce ? 'auto' : 'smooth' })`；否则不抢滚动，显示「回到最新」。

### 2.6 `ProposalCard`

| 交互 | 参数 |
|---|---|
| 出现 | `initial { opacity: 0, y: 8, scale: 0.985 }` → `animate { opacity: 1, y: 0, scale: 1 }`，`spring` |
| 移除（内联态被放弃时） | `exit { opacity: 0, height: 0 }`，`expand`；卡片自身 `overflow: hidden`，间距写在内层，不写在动画元素的 margin 上 |
| 展开/收起改写全文 | 包裹层 `animate={{ height: expanded ? 'auto' : 120 }}`（6 行 × 20px），`expand`；原文折叠高度 40（2 行） |
| 多镜「还有 N 镜」展开 | 新增行 `initial { opacity: 0, height: 0 }` → `{ opacity: 1, height: 'auto' }`，`expand`，行间错开 0.03s |
| 点「采用」 | 按钮内容换成 `.spinner` + 原文字，按钮宽度锁定为点击前的宽度（`minWidth` 取测量值），两个按钮都禁用 |
| 采用成功 | ① 正文区高度收到 0（`expand`），卡片变成一行紧凑态；② 底栏 `<AnimatePresence mode="wait" initial={false}>`：旧底栏 `exit { opacity: 0, y: -4 }`（`quick`），新底栏 `initial { opacity: 0, y: 4 }`（`fade`）；③ 对勾图标 `initial { scale: 0.5, opacity: 0 }` → `{ scale: 1, opacity: 1 }`，`spring`；④ 边框色 CSS 过渡 `.2s var(--ease)` 到 `color-mix(in srgb, var(--ok) 40%, transparent)`；⑤ 对应 `StepOutput` 文本框闪一次（见下） |
| 撤销 | 「撤销」换 `.spinner`；成功后状态标签换成「已撤销」（标签切换同 §2.8），底栏退场 `quick`，文本框再闪一次 |
| 文本框闪烁 | 给 textarea 加一次性 class `.is-updated`：`@keyframes agent-flash { from { background: var(--accent-soft); } to { background: var(--shade); } }`，`.9s var(--ease)`，`animationend` 后移除 class |
| 浮窗内放弃 | 正文收起（`expand`），卡片 `opacity` 到 0.6（`fade`），显示「已放弃」标签 |

### 2.7 `ConflictBar`

```tsx
<AnimatePresence initial={false}>
  {conflict && (
    <motion.div className="conflict-bar" key="conflict"
      initial={reduce ? false : { height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
      transition={reduce ? instant : expand}>
      <motion.div className="warnbox"
        initial={reduce ? false : { y: -4 }} animate={{ y: 0 }} transition={reduce ? instant : expand}>
        …
      </motion.div>
    </motion.div>
  )}
</AnimatePresence>
```

- `.conflict-bar` 只负责高度：`overflow: hidden`，没有 padding/margin；与上方内容的间距写在内层 `.warnbox` 的 `margin-top: 8px` 上，否则展开时最后几帧会跳 8px。
- 冲突出现时，卡片原底栏按 §2.6 的底栏切换方式退场，冲突条的两个按钮取而代之。

### 2.8 `OperationCard`

| 交互 | 参数 |
|---|---|
| 出现 | 同 `ProposalCard` |
| 状态标签切换 | `<AnimatePresence mode="popLayout" initial={false}>`，`key={state}`；`initial { opacity: 0, y: 3 }` → `{ opacity: 1, y: 0 }`，`exit { opacity: 0, y: -3 }`，`quick` |
| 「开始生成」 | 与「采用」相同的按钮加载态；状态离开 `awaiting_approval` 后底栏切换（同 §2.6） |
| 进度 | 现有 `.bar.thin`，宽度由 CSS `transition: width .5s var(--ease)` 驱动；排队中用 `.bar.thin.indet`；数字 `.tabular` |
| 失败项局部重试 | 该行图标按钮换 `.spinner`；成功后该行 `exit { opacity: 0, height: 0 }`（`expand`），其余行 `layout="position"`、`transition={spring}` 补位；再次失败时只把该行错误文字按 `quick` 交叉淡入，不抖动、不闪红 |
| 结果缩略图 | 生成完成的缩略图逐张 `initial { opacity: 0, scale: 0.96 }` → `{ opacity: 1, scale: 1 }`，`{ ...springSmall, delay: i * 0.04 }` |

### 2.9 `WorkflowBoard`

| 交互 | 实现 |
|---|---|
| 节点选中 | 纯 CSS：`border-color`、`box-shadow` 过渡 `.18s var(--ease)`。选中态 `border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft)`。不缩放（缩放会让文字发虚） |
| 节点悬停 | `border-color: color-mix(in srgb, var(--accent) 35%, var(--line-strong))`，`.15s` |
| 连线高亮 | CSS：`transition: stroke .18s var(--ease), stroke-width .18s var(--ease), stroke-opacity .18s var(--ease)`。默认 `stroke: var(--muted); stroke-opacity: .6; stroke-width: 1.5`；与选中节点相连的线 `stroke: var(--accent); stroke-opacity: 1; stroke-width: 2`；有选中节点时其他线降到 `stroke-opacity: .3`。选中相关的 `<path>` 排在最后渲染，压在其他线上面 |
| 拖拽预览 | 跟手 1:1，不加弹簧。`pointermove` 用 `requestAnimationFrame` 合并，每帧最多更新一次预览坐标，节点与连线同一帧更新。拖动中节点加 `data-dragging`：`cursor: grabbing; box-shadow: var(--shadow); z-index: 2`。松手即落位，不做回弹 |
| 键盘微调（Shift + 方向键） | 瞬时移动 12px，节点和连线同帧更新，不做动画 |
| 缩放 | 瞬时。外层尺寸盒与平面缩放无法同步做过渡，强行过渡会让滚动区跳动 |
| 变量面板展开 | `<AnimatePresence initial={false}>` + `motion.section`：`{ height: 0, opacity: 0 }` ↔ `{ height: 'auto', opacity: 1 }`，`expand`；按钮里的 `ChevronDown` CSS 旋转 180°，`.2s var(--ease)` |
| 变量行增删 | 新行 `{ opacity: 0, height: 0 }` → `{ opacity: 1, height: 'auto' }`，删除反向，`expand`；已有行不播动画 |

### 2.10 只允许这些属性做动画

`transform`（`x/y/scale`）、`opacity`，以及白名单里的高度动画：`ProposalCard` 正文与多镜行、`ConflictBar`、变量面板与变量行、`OperationCard` 失败项行。CSS 侧另允许 `border-color`、`box-shadow`（选中环）、`stroke*`、`background`（闪烁）、进度条 `width`。其他属性一律不做过渡。

---

## 3. 组件规格

通用约束：

- 文案全部来自 `agentCopy.ts`，下文用 `C.` 表示 `AGENT_COPY.`。
- 每个组件的「上限」是硬上限，超出部分折叠或省略，不得加行。
- 不得有副标题、说明小字、运行时状态（进程、会话复用/恢复、模型 ID）、内部 ID。
- 用户数据容器（用户气泡、提示词正文、diff、文本框、作品名）加 `data-user-content`，终验扫描会跳过这些区域（§5.4）。

### 3.1 `WorkflowBoard`

```
section.graph-shell.glass                       圆角 var(--r-lg)，overflow hidden
├─ header.graph-heading                         高 44px，下边框 var(--line)
│  ├─ GitBranch(16, --fg-soft)
│  ├─ h3  C.board.title                         13.5px / 650
│  ├─ span.grow
│  ├─ button.graph-vars[aria-expanded]          C.board.variables + 数量(.tabular) + ChevronDown(13)
│  └─ div.graph-zoom                            左边框分隔
│     ├─ button.iconbtn.sm  aria=C.board.zoomOut   Minus
│     ├─ button.graph-scale aria=C.board.zoomReset C.board.zoomValue(scale)
│     └─ button.iconbtn.sm  aria=C.board.zoomIn    Plus
├─ AnimatePresence → motion.section.wf-variables   见下
├─ div.graph-viewport[tabindex=0] aria=C.board.canvas
│  └─ div（尺寸盒）> div.graph-plane
│     ├─ svg.graph-wires > path（选中相关的排最后）
│     └─ button.graph-node × n
│        ├─ span.graph-node-type   lucide 图标(13) + C.board.nodeTypes[type] + 运行状态 .dot + 序号(.tabular，右对齐)
│        ├─ b                      步骤名（去掉序号前缀，1 行省略）
│        └─ span.graph-node-meta   C.board.nodeDetail.*（1 行）
├─ div.graph-refs                               有参考图时才渲染
│  └─ button × ≤8  aria=C.board.refAlt(stepName) > img
└─ footer.graph-footer                          高 36px
   ├─ 有选中：span.graph-selection(节点名) + button C.board.editNode + button C.board.askAgent
   └─ 无选中：span C.board.hint 或 C.board.emptyHint
```

样式：
- 视口：`background-color: var(--shade)`，点阵 `radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--muted) 35%, transparent) .8px, transparent .9px)`，16px 网格。
- 节点：166×68，`border-radius: var(--r-sm)`，`background: var(--glass-solid)`，`border: 1px solid var(--line-strong)`。类型行 11.5px `--fg-soft`；标题 13.5px / 620 `--fg`；元信息 11.5px `--fg-soft`。停用节点 `opacity: .55` 且边框 `dashed`，aria-label 末尾追加 `C.board.nodeOff`。
- 端口圆点（`::before/::after`）：`border: 1.5px solid var(--muted); background: var(--glass-solid)`，选中时边框 `--accent`。
- 运行状态点：`pending` 不显示；`running` → `.dot.busy`；`done` → `.dot.ok`；`error` → `.dot.bad`。
- 参考图条：缩略图 72×48，`border-radius: var(--r-sm)`，`background: var(--shade-2)`，**不叠文字**，不加 `title`。

变量面板：

```
motion.section.wf-variables                      内边距 10px 14px，下边框 var(--line)
├─ div.var-row × n                               高 32px
│  ├─ span.mono.var-name                         变量名
│  ├─ span.var-value[data-user-content]          值（1 行省略；布尔值显示 C.vars.booleanValues）
│  ├─ button.iconbtn.sm aria=C.vars.copyRef(name)   Copy → 复制 {{vars.name}}，toast C.toast.refCopied
│  ├─ button.iconbtn.sm aria=C.vars.edit(name)      Pencil
│  └─ button.iconbtn.sm aria=C.vars.remove(name)    Trash2
├─ 无变量时：span.var-empty C.vars.empty（--muted）
├─ button.btn.sm.ghost  Plus + C.vars.add
└─ form.var-form（编辑中）
   ├─ input aria=C.vars.nameLabel  placeholder=C.vars.namePlaceholder
   ├─ select aria=C.vars.typeLabel  选项 C.vars.types
   ├─ input/select aria=C.vars.valueLabel
   ├─ button.btn.sm.primary C.vars.save
   ├─ button.btn.sm.ghost   C.vars.cancel
   └─ span.var-error[role=alert]  C.vars.errors.*（12.5px，--bad 图标 + --fg 文字）
```

上限：标题栏 1 行；节点 3 行；每个变量行 3 个图标按钮；底栏 1 行、最多 2 个按钮；参考图最多 8 张。

删除：原型的 `<small>在提示词中用 {{vars.name}} 引用</small>`。`{{vars.*}}` 写法只在用户点「复制引用」时进剪贴板，不在界面上显示。

### 3.2 `WorkflowAgent`

启动按钮：

```
button.agent-launch.glass  aria-haspopup=dialog aria-expanded=false
├─ MessageSquare(17, --accent)
├─ span  C.agent.launcher                        13.5px / 620，--fg
├─ 处理中：span.dot.busy                         aria-label 改为 C.agent.launcherBusy
└─ 有未读回复：span.badge-dot                    aria-label 改为 C.agent.launcherUnread
```

高 40px（≤760px 为 44px），`padding: 0 14px 0 12px`，`border-radius: 14px`，`z-index: 31`。

面板：

```
motion.section.workflow-agent.glass[data-dock][role=dialog][aria-modal=false][aria-labelledby]
├─ header.agent-head                             高 52px；整行（按钮除外）是拖动区，sheet 态不可拖
│  ├─ h2  C.agent.title                          15px / 650
│  ├─ Seg  选项 C.agent.tabs.chat / C.agent.tabs.plugins   ariaLabel=C.agent.tabs.aria
│  ├─ span.grow
│  ├─ button.iconbtn.sm  aria=C.agent.moveAside（sheet 态为 moveUp/moveDown）  PanelRight/ArrowUpDown
│  └─ button.iconbtn.sm  aria=C.agent.collapse   Minus
├─ 对话 Tab：
│  ├─ div.agent-context  aria=C.agent.context.aria     高 32px，背景 var(--shade)
│  │  ├─ Workflow(14) + 工作流名 [+ ChevronRight + 步骤名] [+ ChevronRight + C.agent.context.shot(n)]
│  │  └─ 有选中时：button.iconbtn.sm aria=C.agent.context.clear  X
│  ├─ div.agent-log[role=log][aria-live=polite] aria=C.agent.status.historyAria
│  │  ├─ 空态：div.agent-empty
│  │  │  ├─ h3  C.agent.empty.workflow | C.agent.empty.step
│  │  │  └─ button × ≤3  建议的 label + ChevronRight；点击把 prompt 填入输入框
│  │  ├─ div.agent-exchange × n                  见下
│  │  └─ button.chip.agent-jump  C.agent.status.jumpLatest（用户上滚时）
│  └─ form.agent-compose
│     ├─ textarea rows=2  aria=C.agent.composer.aria  placeholder=C.agent.composer.placeholder(Step)
│     └─ button.agent-send  aria=C.agent.composer.send(ArrowUp) | C.agent.composer.stop(Square)
└─ 插件 Tab：AgentPlugins
```

一轮对话：

```
div.agent-exchange
├─ p.agent-user[data-user-content]               用户原话
├─ div.agent-tools                               徽章 ≤4，超出显示 .tag「+N」，点击展开
│  └─ span.tag.agent-tool × n                    图标(12) + toolLabel(name, op)
├─ p.agent-answer[data-user-content=answer]      模型回复，pre-wrap
├─ span.tag.ok.agent-applied                     Check + C.agent.applied.*（≤1 个）
├─ ProposalCard variant=panel × ≤2               更多提案只显示最新 2 个
├─ OperationCard × ≤1
├─ ConflictBar（编辑器在这一轮里被改动：C.agent.stale.*）
├─ 出错：div.agent-error                          CircleAlert(14, --warn) + errorCopy(code).text（--fg）
│  └─ div.agent-links  ERROR_ACTION_LABELS[action]；action 不是 edit 时再加 ERROR_ACTION_LABELS.edit，合计 ≤2
├─ 进行中：span.agent-working  .spinner + C.agent.status.working
└─ button.btn.sm  Play + C.agent.run.*（≤1 个）
```

样式：
- 面板 `background: var(--glass-solid)`，`border-radius: var(--r-lg)`，`box-shadow: var(--shadow-lg), inset 0 1px 0 var(--glass-hi)`；`sheet` 态同样圆角。
- 用户气泡：`background: var(--accent-soft)`，`color: var(--fg)`，`border-radius: 14px 14px 4px 14px`，`padding: 8px 12px`，最大宽 88%，右对齐。
- 回复：不加气泡，直接排文字（13.5px / 1.6，`--fg`）。
- 工具徽章：`.tag` 基础上 `height: 22px; padding: 0 8px; background: var(--shade); color: var(--fg-soft); font-weight: 550`。进行中 `.spinner`（10px）；成功 `Check` 着 `--ok`；失败 `CircleAlert` 着 `--warn`，aria-label 为 `C.agent.tools.failedAria(label)`。相邻重复的同名徽章合并，显示 `C.agent.tools.repeat(n)`。
- 工具徽章的标签由前端 `toolLabel(event.name, event.op)` 计算，**不使用服务端下发的 `label`**。后端 `tool` 事件需带 `op` 字段。
- 停止：`state === 'stopped'` 显示一行 `C.agent.status.stopped`（`--fg-soft`），不按错误样式显示。
- 删除：`agent-runtime`（`dsh · 已启动`、`title="dsh PID …"`、`DeepSeek Harness`）整块删除，不留替代；`session` 事件不在界面上体现。
- `TIMING_REQUEST` 改为 `C.agent.suggestions.timing.prompt`；`tryTiming` 不得清空输入框里的草稿（`send(text)` 只在发送的是输入框内容时才 `setInput('')`）。
- 宿主 `.run` 处于 `inert` 时，浮窗同步禁用输入与发送（Portal 不受 `inert` 影响，需要显式传入锁定状态）。

上限：标题栏 1 行，最多 2 个图标按钮 + 1 个 Seg；上下文 1 行；空态 1 个标题 + 3 条建议；每轮徽章 4 个、标签 1 个、链接 2 个、运行按钮 1 个。

建议条目的选取（按顺序取前 3 条）：

| 上下文 | 建议 |
|---|---|
| 未选节点 | `suggestions.workflow` 三条 |
| 选中 `llm_script` | `sceneCount(当前为 5 时取 3，否则取 5)`、`polish`、`step` |
| 选中 `h3_prompt` | `polish`、`step` |
| 选中其他节点 | `step` |
| 计时插件已启用 | 在列表末尾追加 `timing`（仍不超过 3 条，挤掉最后一条） |

### 3.3 `AgentPlugins`

```
div.agent-plugins
├─ 读取中：span.agent-working  .spinner + C.plugins.loading
├─ 读取失败：div.agent-error  CircleAlert + C.plugins.loadFailed + button.mini-link C.plugins.retry
├─ article.agent-package × n                     背景 var(--shade)，圆角 var(--r)，内边距 12px
│  ├─ div.package-heading
│  │  ├─ span.package-icon  Timer(20)            36×36，圆角 var(--r-sm)，背景 var(--accent-soft)，图标 --accent
│  │  ├─ b  PLUGIN_COPY[id]?.name ?? 服务端 name  13.5px / 620
│  │  ├─ span.grow
│  │  └─ 已安装：span.tag(.ok)  C.plugins.state.enabled | disabled
│  ├─ p  PLUGIN_COPY[id]?.description            1 行省略，--fg-soft
│  └─ div.package-actions
│     ├─ 未安装：button.btn.sm.primary  Download + C.plugins.install（进行中 .spinner + C.plugins.installing）
│     └─ 已安装：
│        ├─ 已启用：button.btn.sm.primary  Play + C.plugins.tryTiming
│        ├─ button.btn.sm  C.plugins.enable | C.plugins.disable
│        └─ button.iconbtn.sm  aria=C.plugins.removeAria(name)  Trash2   右对齐
└─ details.agent-builtins                        默认折叠
   ├─ summary  ChevronRight + C.plugins.builtins + 数量(.tabular)
   └─ ul（两列网格） > li × n  toolLabel(id)      只显示中文标签
```

上限：每个插件 1 行标题 + 1 行描述 + 最多 2 个文字按钮和 1 个图标按钮。

删除：`Studio · v{version}`；内置工具列表里的 `<code>{id}</code>`；插件操作的错误原文（统一 `errorCopy(code)`）。安装、启用、停用、卸载成功后用 `C.toast.plugin*` 提示。

### 3.4 `ProposalCard`（浮窗与 `StepOutput` 共用）

```ts
interface ProposalCardProps {
  variant: 'panel' | 'inline'
  field: ProposalField
  shots: readonly { n: number; before: string; after: string }[]   // 独立创作台提案为 n = 0 的单条；标题只取 n > 0 的镜号
  refs: readonly { id: string; thumb: string; label: string }[]
  state: ProposalState
  conflict?: ConflictKind
  onApply: () => void; onReject: () => void; onUndo: () => void
  onRegenerate: () => void; onKeep: () => void; onDismiss?: () => void
}
```

```
motion.article.proposal[data-state][data-variant]
├─ header.proposal-h                             1 行
│  ├─ b  C.proposal.title(shots 的 n, field)      12.5px / 620，省略
│  ├─ span.grow
│  └─ 非 pending：span.tag(.ok | 无)  C.proposal.state[state]（applied 时前面带 Check 图标）
├─ motion.div.proposal-body                      高度动画容器
│  ├─ 单镜：div.proposal-diff[data-user-content]
│  │  ├─ p.proposal-before  span.lbl C.proposal.before + 原文（折叠 2 行）
│  │  ├─ p.proposal-after   span.lbl C.proposal.after  + 改写（折叠 6 行，新增片段用 <ins>）
│  │  └─ 超过 6 行：button.mini-link  C.proposal.expand | collapse
│  ├─ 多镜：div.proposal-shot × ≤3              每行：shotLabel(n) + 改写（折叠 3 行），原文默认隐藏，展开后显示
│  │  └─ 超过 3 镜：button.mini-link C.proposal.moreShots(rest)
│  └─ div.proposal-refs  aria=C.proposal.refsAria(n)
│     └─ img × ≤4  alt=C.proposal.refAlt(label)   36×36，圆角 8px；超出显示 span C.proposal.moreRefs(rest)
├─ ConflictBar（有 conflict 时；显示期间隐藏下方底栏）
└─ footer.proposal-f                             右对齐，按钮 ≤2
```

底栏按状态：

| state | 按钮 |
|---|---|
| `pending` | `btn.sm.ghost` `C.proposal.reject` · `btn.sm.primary` `C.proposal.apply`（多镜 `applyShots(n)`） |
| `applying` | 同上，均禁用，主按钮显示 `.spinner` |
| `applied` | `btn.sm.ghost` `C.proposal.undo`；内联态另有 `iconbtn.sm` `X`（aria `C.proposal.dismiss`） |
| `undoing` | `C.proposal.undo` 显示 `.spinner` |
| `undone` | 浮窗态无按钮；内联态只有关闭 |
| `rejected` | 浮窗态无按钮；内联态整卡移除 |
| `expired` | `btn.sm` `C.proposal.regenerate` |

样式：
- `background: var(--glass-solid)`，`border: 1px solid var(--line)`，`border-radius: var(--r)`，`padding: 10px 12px`，无阴影。内联态放在 `.scene` 里，与文本框间距 8px。
- 正文 13px，`line-height: 20px`，`--fg`；原文 `--fg-soft`。`.lbl` 标签同行前置，12px `--muted`。
- `<ins>`：`background: var(--accent-soft); color: var(--fg); text-decoration: none; border-radius: 3px`。原文里被删的片段 `<del>`：`color: var(--muted); text-decoration: line-through`。
- diff 算法：按字符做最长公共子序列，相邻改动合并成片段，长度 <2 的孤立相同字符并入两侧改动。改动字数超过全文 60% 时不做高亮，只显示原文与改写两段。
- `applied`：边框 `color-mix(in srgb, var(--ok) 40%, transparent)`，正文收起成一行紧凑态。

反馈：
- 浮窗里采用成功：`toast(C.toast.appliedShots(nums), 'ok', { label: C.toast.undo, fn: undo })`。
- 内联采用成功：不弹 toast，卡片本身就是反馈；对应文本框按 §2.6 闪一次。
- 撤销被拒（字段已再次修改）：`toast(C.toast.undoBlocked, 'err')`，卡片保持 `applied`。

上限：标题 1 行；原文 2 行；改写 6 行；多镜 3 行；参考图 4 张；按钮 2 个。

### 3.5 `ConflictBar`

```ts
type ConflictKind =
  | { kind: 'changed' }
  | { kind: 'shots'; nums: readonly number[] }
  | { kind: 'partial'; applied: number; nums: readonly number[] }
  | { kind: 'stale' }                              // 浮窗：工作流在这一轮里被改动
```

```
motion.div.conflict-bar[role=status]             只负责高度，无内边距
└─ motion.div.warnbox                            margin-top 8px；文字 --fg
   ├─ CircleAlert(14, --warn)
   ├─ span.grow  文案（≤2 行）
   │    changed → C.conflict.changed
   │    shots   → C.conflict.shots(nums)
   │    partial → C.conflict.partial(applied, nums)
   │    stale   → C.agent.stale.text
   ├─ button.btn.sm.primary  C.conflict.regenerate（stale 时为 C.agent.stale.resend）
   └─ button.btn.sm.ghost    C.conflict.keep（stale 时为 C.agent.stale.dismiss）
```

`flex-wrap: wrap`；空间不足时两个按钮整体换到第二行并右对齐。上限：1 段文字、2 个按钮。不显示版本号、冲突字段名或原因说明。

### 3.6 `OperationCard`

```ts
interface OperationCardProps {
  kind: OperationKind
  state: OperationState
  total: number; done: number
  meta: readonly string[]          // 已格式化的模型名、尺寸、帧数，最多 3 项，用 · 连接
  refs: readonly { id: string; thumb: string; label: string }[]
  results: readonly { id: string; thumb: string; label: string }[]
  failed: readonly { n: number; code: HarnessErrorCode; retrying: boolean }[]
  needsCompute: boolean
  onConfirm: () => void; onCancel: () => void; onStop: () => void
  onRetryFailed: () => void; onRetryItem: (n: number) => void; onView: () => void
  onConnect: () => void
}
```

```
motion.article.op-card[data-state]               样式同 .proposal
├─ header.op-h
│  ├─ ImageIcon | Film (15, --fg-soft)
│  ├─ b  C.operation.title[kind](total)
│  ├─ span.grow
│  └─ span.tag.{tone}  C.operation.state[state]   unknown 时标签前加 .spinner
├─ p.op-meta  meta.join(' · ')                   1 行，12.5px --fg-soft
├─ div.proposal-refs                             生成前显示参考图，完成后换成结果，均 ≤4 + 「+N」
├─ queued / running / partial：div.op-progress
│  ├─ div.bar.thin(.indet 用于 queued) > i
│  └─ span.tabular  C.operation.progress(done, total)
├─ failed.length > 0：ul.op-items                ≤3 行，超出显示 C.operation.moreItems(rest)
│  └─ li  C.operation.item(n) + errorCopy(code).text + button.iconbtn.sm aria=C.operation.retryItem RotateCcw
├─ needsCompute：div.warnbox  CircleAlert + C.operation.needsCompute + button.btn.sm C.operation.connect
└─ footer.op-f                                   右对齐，按钮 ≤2
```

状态色：`awaiting_approval` → `.tag.run`；`queued`、`canceled`、`unknown` → `.tag`；`running` → `.tag.run`；`partial` → `.tag.warn`；`done` → `.tag.ok`；`failed` → `.tag.bad`。

底栏按状态：

| state | 按钮 |
|---|---|
| `awaiting_approval` | `ghost` `C.operation.cancel` · `primary` `C.operation.confirm`（`needsCompute` 时禁用主按钮） |
| `queued` | `ghost` `C.operation.cancel` |
| `running` | `ghost` `C.operation.stop` |
| `partial` | `primary` `C.operation.retryFailed(n)` · `btn` `C.operation.view` |
| `done` | `btn` `C.operation.view` |
| `failed` | `primary` `C.operation.retryFailed(n)` |
| `canceled`、`unknown` | 无 |

反馈：入队 `toast(C.toast.queued, 'ok')`；全部完成且浮窗收起时 `toast(C.toast.operationDone(n, kind), 'ok')`；有失败项且浮窗收起时 `toast(C.toast.operationFailed(n), 'err')`。

不显示：费用、GPU 型号、队列位置、任务或操作编号、「需要你确认才会执行」之类的说明。确认按钮的文字本身已经说明动作。

上限：标题 1 行；元信息 1 行；缩略图 4 张；失败项 3 行；底栏按钮 2 个（失败行内的重试图标不计）。

### 3.7 `StepOutput` 内联「AI 改写」

只在 `llm_script`（字段 `keyframe_prompt`）和 `h3_prompt`（字段 `video_prompt`）的逐镜列表里出现。

```
div.step-out
├─ div.row.between
│  ├─ span.lbl  产出（沿用现有文案）
│  └─ 镜头数 ≥2：button.btn.sm.ghost  WandSparkles(13) + C.stepAi.rewriteAll
└─ div.scenes > div.scene × n
   ├─ div.scene-h
   │  ├─ b  序号. 标题
   │  ├─ span.grow
   │  └─ button.btn.sm.ghost  aria=C.stepAi.triggerAria(n)  WandSparkles(13) + C.stepAi.trigger
   │       生成中：.spinner + C.stepAi.generating，禁用
   ├─ textarea[data-user-content]                现有文本框
   ├─ AnimatePresence → motion.form.shot-ai      高度展开（expand）
   │  ├─ input  placeholder=C.stepAi.placeholder  回车提交；留空则发送 C.stepAi.defaultInstruction
   │  ├─ button.btn.sm.primary  C.stepAi.submit
   │  └─ button.iconbtn.sm  aria=C.stepAi.cancel  X
   ├─ AnimatePresence → ProposalCard variant=inline   ≤1 个，新结果替换旧结果
   └─ small → 改为 span.scene-meta（--fg-soft，见 §1.3）
```

行为：
- 运行中（`disabled`）时触发按钮隐藏。
- 生成期间文本框保持可编辑。如果用户在生成期间改了这一镜，结果返回后提案直接带 `ConflictBar`（`changed`）。
- 「全部改写」生成一个多镜提案，显示在 `step-out` 顶部，各镜不再单独出卡。
- 节点里的「AI 改写」与浮窗共用同一个 `ProposalCard` 和同一组服务端接口（改写 → 提案 → 采用 → 撤销）。

上限：每镜 1 个触发按钮、1 个提案；步骤顶部 1 个按钮。

---

## 4. 文案

### 4.1 写法

1. 先说结果。「已更新分镜」「约 25.8 秒」「原内容已变」。
2. 能用 2–6 个字说完就不用句子。按钮是动词（「采用」「重新生成」「开始生成」），状态是「已 + 动词」或「…中」。
3. 出错时说发生了什么、能做什么，不解释原因链，不道歉。
4. 用「你」，不用「您」。不用「请」开头的命令句，按钮已经表达了动作。
5. 数字和中文之间留一个空格（「3 个镜头」「第 3 镜」）；时长用「约 N 秒」；尺寸用「1024 × 768」。
6. 一个概念只用一个词：助手（不叫编排助手、Copilot、Agent）、提示词（不叫 Prompt）、作品（不叫 round）、镜（「第 3 镜」，计数时用「3 个镜头」）、采用（不叫应用/接受；「已应用」只作采用后的状态）、算力（不叫 Colab、GPU 会话）。
7. 不显示服务端返回的 `error`/`message` 原文。按 `code` 走 `errorCopy()`；没有 `code`（断网、超时）按 `internal_error`。

### 4.2 禁词

完整列表在 `agentCopy.ts`：`BANNED_PHRASES`（防御性话术）、`BANNED_PATTERNS`（「不是…而是…」等句式）、`BANNED_INTERNAL_TERMS`（内部契约）、`BANNED_IN_ANSWERS`（模型回复里的内部词）。检测函数为 `findBannedTerms(text, surface)`。

两类问题：

- 防御与免责：无法证明、没有证据、不是…而是…、估算、剪辑前、仅在…时、仅供参考、版本匹配、本轮、本次、工具调用、已暂存、由编辑器采用、请按工具定义、可能会产生费用、无法确认、请注意、温馨提示、抱歉、作为 AI、我将、为您、您、以下是、需要注意的是、理论上、不保证、尽力、系统检测到、是否确认。
- 内部契约：dsh、PID、CAS、idempotency、proposal_id、operation_id、undo_id、shot_id、run_id、step_id、round_id、job_id、schema、native session、Harness、revision、readset、writeset、token、JSON、API、DeepSeek、pnpm、profile、`studio_*` 工具名、`{{vars.*}}` 语法说明、LLM、Prompt。

### 4.3 坏例 → 好例

| 原型 / 坏例 | 改为 | 字典键 |
|---|---|---|
| `dsh · 已启动`、`title="dsh PID 35175"`、`DeepSeek Harness` | 删除，不留替代 | — |
| 编排助手 | 助手 | `agent.title` |
| 按配置估算，剪辑前片长 | 约 25.8 秒 | `approxDuration()` |
| 本轮工具调用已完成 | 不显示，徽章已表达 | — |
| 已暂存，由编辑器采用 | 已更新分镜 | `agent.applied.*` |
| 仅在版本匹配时成功 | 删除；冲突发生时显示「原内容已变」 | `conflict.changed` |
| 请按工具定义重试 | 不上屏（模型自行修正参数） | — |
| 可能会产生费用 | 删除；确认按钮写「开始生成」 | `operation.confirm` |
| 你在这轮对话中改动了工作流。本轮操作未应用，请按最新草稿重试。 | 工作流刚有改动，这次修改没有套用 ［重新发送］ | `agent.stale.*` |
| 请先保存当前修改，再发送指令 | 修改还没保存好，稍后再发 | `agent.unsaved` |
| 未能读取对话记录，重新打开浮窗可重试 | 对话记录没加载出来 | `toast.historyFailed` |
| 正在处理… / 正在整理结果… | 处理中 | `agent.status.working` |
| 本轮已停止。 | 已停止 | `agent.status.stopped` |
| 未能完成这轮编排 | 按错误码显示，如「模型这次没有回应」［重试］ | `errorCopy()` |
| 运行此工作流 / 运行指定步骤 | 运行 / 运行「关键帧」 | `agent.run.*` |
| 移动浮窗到另一侧 / 收起编排助手 | 移到另一侧 / 收起 | `agent.moveAside` / `agent.collapse` |
| 改为讨论整个工作流 | 改为整个工作流 | `agent.context.clear` |
| 给编排助手的指令 / 描述你的工作流或修改… | 给助手的话 / 说说想怎么改 | `agent.composer.*` |
| `<small>在提示词中用 {{vars.name}} 引用</small>` | 删除，改为每行一个「复制引用」图标 | `vars.copyRef` |
| 名称以英文字母或下划线开头，可含数字，最多 48 个字符 | 以字母或下划线开头，只含字母、数字和下划线 | `vars.errors.name` |
| 当前已有 ID 为 vars 的步骤，占用了变量名称空间 | 有步骤占用了 vars 这个名字，先给它改名 | `vars.errors.reserved` |
| 布尔 | 开关 | `vars.types.boolean` |
| 选择节点可编辑参数，拖动可调整布局。 | 点选节点编辑，拖动调整位置 | `board.hint` |
| 在下方添加步骤，或让编排助手搭建工作流。 | 在下方添加步骤，或让助手来搭 | `board.emptyHint` |
| `title="选择素材节点 · …"` + 缩略图叠提示词 | 删除；aria 为「关键帧 的参考图」 | `board.refAlt` |
| `Studio · v1.0.0` | 删除 | — |
| 内置工作流工具 + `<code>studio_read_workflow</code>` | 内置能力，只列中文标签 | `plugins.builtins` |
| 按分镜数量和视频帧数估算剪辑前片长。 | 按镜头数和帧数算出片长 | `PLUGIN_COPY` |
| 试算片长 | 算片长 | `plugins.tryTiming` |
| 请调用镜头计时尺工具 studio_shot_timing，按当前分镜数量和视频帧数估算剪辑前片长。 | 算一下现在的片长 | `agent.suggestions.timing.prompt` |
| `{label}失败`（可见文字） | 只用图标表达，aria 读「{label}失败」 | `agent.tools.failedAria` |

### 4.4 错误码

18 个错误码的文案与动作见 `HARNESS_ERROR_COPY`。呈现位置：

| 触发处 | 呈现 |
|---|---|
| 对话流 `error` 事件 | 该轮的 `.agent-error` 行 + 最多 2 个链接 |
| `ProposalCard` 的采用/撤销/重新生成 | `revision_conflict`、`shot_conflict` → 卡内 `ConflictBar`；其他 → `toast(text, 'err')` |
| `OperationCard` | `colab_unauthed` → 卡内 `needsCompute`；`queue_full`、`approval_required` → `toast`；单项失败 → 失败行 |
| 插件页 | 卡片下方 `.agent-error` 行 |
| `turn_stopped` | 不按错误显示，只显示「已停止」 |

### 4.5 `copilot.py` 的 `SYSTEM` 语调

下面这段原样放进 `SYSTEM`，位置固定在工具规则之后，不随轮次变化（保持前缀缓存命中）：

```text
说话方式：
- 用中文，像一起做片的同事那样直接说。先给结果，默认不超过三句。
- 做完了就说做了什么，例如「第 3 镜改成黄昏逆光了，看下面的卡片。」
- 没做成就说卡在哪、需要对方做什么，例如「第 3 镜刚被你改过，要我按新内容重写吗？」
- 数字直接给，例如「约 25.8 秒：5 镜，每镜 129 帧，24 fps。」
- 不提工具名、参数名、编号、版本号、进程和系统机制。
- 不写铺垫和免责：不说「无法保证」「仅供参考」「需要注意的是」「作为 AI」「本轮」「您」，不用「不是……而是……」。
- 候选稿和待确认的生成由界面卡片展示，回复里一句话点明，不重复贴全文。
- 不用 Markdown 标题和表格；三项以上并列时才用短横线列表。
- 工具报错时自己修正参数再试；仍然不行，用一句话告诉对方结果。
```

范例（同样固定写入 `SYSTEM`，最多 5 条）：

| 用户 | 助手的做法 | 回复 |
|---|---|---|
| 把第 3 镜改得更有电影感 | 读分镜 → 改写提示词 | 第 3 镜写了一版，低机位、浅景深，看下面的卡片。 |
| 改成 5 个镜头 | 修改工作流 | 分镜改成 5 个镜头了，下游关键帧会跟着出 5 张。 |
| 片子现在多长 | 计算片长 | 约 25.8 秒：5 镜，每镜 129 帧，24 fps。 |
| 用这些提示词出关键帧 | 准备生成 → 提交生图 | 4 张关键帧准备好了，点「开始生成」就进队列。 |
| （算力未连接时）开始生成视频 | 提交视频，收到 colab_unauthed | 还没连接算力，连上后我再提交。 |

---

## 5. 终验

Codex 用 Chrome `--headless=new` + CDP 采集，交回截图、动效帧、扫描结果和前端 diff。设备像素比：桌面 2，窄屏 3。主题用 `data-theme='light' | 'dark'` 切换。

### 5.1 静态截图矩阵

每个状态 × {1440×900, 390×844} × {浅色, 深色}，共 21 × 4 = 84 张。

| 编号 | 状态 |
|---|---|
| S01 | 启动按钮常态（浮窗收起） |
| S02 | 启动按钮：处理中 / 有未读 |
| S03 | 浮窗空态，未选节点 |
| S04 | 浮窗空态，选中 `llm_script` 节点（上下文行带步骤名） |
| S05 | 对话进行中：用户气泡 + 进行中徽章 + 「处理中」 |
| S06 | 对话完成：成功与失败徽章、「已更新」标签、运行按钮 |
| S07 | 错误回复：`model_unconfigured` + 「去设置」「重新编辑」 |
| S08 | 单镜提案待采用（diff 高亮 + 参考图） |
| S09 | 多镜提案（3 行 + 「还有 N 镜」） |
| S10 | 提案已应用（紧凑态 + 撤销）+ 带撤销的 toast |
| S11 | 冲突条：`partial` |
| S12 | 操作卡待确认（含 `needsCompute` 变体） |
| S13 | 操作卡生成中（进度条） |
| S14 | 操作卡部分失败（失败行 + 重试） |
| S15 | 插件页：已安装已启用 + 内置能力展开 |
| S16 | 节点图：选中节点、连线高亮、变量面板展开 |
| S17 | 节点拖动中 |
| S18 | `StepOutput`：AI 改写输入框展开 + 内联提案 |
| S19 | 1440：浮窗拖到左侧松手后（右侧无空白）；390：浮窗移到上方 |
| S20 | 浮窗 Tab 停在「插件」 |
| S21 | `prefers-reduced-motion: reduce` 下的 S03 与 S10 |

### 5.2 动效帧

用 CDP `Animation.setPlaybackRate(0.1)` 放慢后按真实时间点截帧，或用 `Emulation.setVirtualTimePolicy` 逐帧推进。只在 1440 浅色下采集，另取一组 390 的 M1。

| 编号 | 交互 | 采帧时刻（ms） | 通过条件 |
|---|---|---|---|
| M1 | 启动按钮 → 浮窗展开 | 0 / 50 / 100 / 160 / 240 / 400 | 100ms 时 `opacity ≥ .8` 且 `scale ≥ .985`；240ms 已稳定（`|scale − 1| < .005`）；离启动按钮最近的角位移最小；无回弹 |
| M2 | 浮窗收起 | 0 / 50 / 100 / 200 / 300 | 300ms 内移出 DOM；退场期间主区不重排 |
| M3 | 对话 ↔ 插件 | 0 / 80 / 160 / 240 | 指示块连续滑动，240ms 已到位；不出现两屏内容叠加 |
| M4 | 新一轮对话 | 0 / 60 / 120 / 200 / 320 | 气泡从右下长出；徽章逐个出现，间隔约 40ms |
| M5 | 采用提案 | 0 / 80 / 160 / 260 / 400 / 900 | 260ms 正文已收起；底栏切换无空白帧；文本框闪烁 900ms 内结束 |
| M6 | 冲突条展开 | 0 / 90 / 180 / 260 | 高度单调增加，最后一帧不跳 |
| M7 | 操作卡状态切换 + 失败项重试成功 | 0 / 80 / 160 / 260 | 行移除时其余行平滑补位 |
| M8 | 选中节点 + 展开变量面板 | 0 / 90 / 180 / 260 | 选中环与连线同时变色；面板高度单调增加 |
| M9 | reduced motion 下 M1、M5 | 0 / 16 | 16ms 时已是终态 |

性能：采集 M1–M8 时同时录 Performance trace。动画期间主线程单个任务不超过 50ms，帧间隔 p95 ≤ 20ms；除 §2.10 白名单外不得出现 layout 类属性动画。

### 5.3 通过标准

红线，任意一条不过即退回：

| 编号 | 检查 | 方法 |
|---|---|---|
| R1 | 界面文字零禁词 | §5.4 扫描，`findBannedTerms(text, 'chrome')` 结果为空 |
| R2 | 模型回复零禁词 | 回放 S05–S14 的对话，`findBannedTerms(answer, 'answer')` 结果为空 |
| R3 | 无裸色值、无新阴影、组件无中文字面量 | §1.2 的四条 `rg` 命令零输出 |
| R4 | 拖到左侧后右侧无空白 | 1440 下 S19 时 `.wf` 的 `padding-right` 为 `0px` |
| R5 | 390 无横向滚动，浮窗完整在视口内 | `scrollWidth ≤ 390`；浮窗 `getBoundingClientRect()` 四边都在视口内 |
| R6 | 对比度 | 正文 ≥4.5:1，≥13px 且字重 ≥600 的控件文字 ≥3:1，浅深两套都测 |
| R7 | reduced motion 无中间帧 | M9 |
| R8 | 信息上限 | 逐组件核对 §3 的行数与按钮数 |
| R9 | 无运行时信息 | DOM 里不存在 `.agent-runtime`，没有任何 `title` 包含 PID、进程、会话状态 |

评分（红线全过后，满分 100，≥90 通过）：

| 维度 | 分值 | 看什么 |
|---|---|---|
| 视觉一致性 | 25 | 与 `.glass`、`.btn`、`.tag` 等现有控件是否同一套语言；浅深色是否都干净；圆角、间距是否在规定档位 |
| 动效 | 25 | M1–M8 的手感、原点、时长、有无掉帧与跳动 |
| 文案 | 20 | 是否简短直接、术语一致；错误是否有可执行动作 |
| 响应式 | 15 | 1440 停靠、761–1279 浮动、390 底部卡片三档是否都成立 |
| 可达性 | 15 | 键盘可达、焦点可见与归还、aria 标签完整、窄屏点击区 ≥36px |

### 5.4 文案扫描范围

- `chrome`：`.agent-launch`、`.workflow-agent`、`.graph-shell`、`.step-out`、`.toasts` 内的全部文本节点，以及 `aria-label`、`title`、`placeholder`、`alt`。跳过带 `data-user-content` 的元素及其子树，跳过 `textarea`/`input` 的值。
- `answer`：所有 `[data-user-content=answer]` 的文本。
- 扫描结果连同命中位置（选择器 + 文本片段）写入终验报告。

---

## 6. 交付清单（Codex）

| 文件 | 内容 |
|---|---|
| `web/src/ui/motion.ts` | 新建，§2.1 |
| `web/src/ui/Overlay.tsx` | 从 `motion.ts` 导入参数；`Seg` 支持 reduced motion |
| `web/src/features/workflow/workbench.css` | 按 §1、§3 重写，删除 §1.2 列出的写法，加入 `--agent-w` 与 `data-dock` 规则 |
| `WorkflowBoard.tsx`、`WorkflowAgent.tsx`、`AgentPlugins.tsx` | 按 §3.1–3.3 改造，文案改用 `agentCopy.ts` |
| `ProposalCard.tsx`、`ConflictBar.tsx`、`OperationCard.tsx` | 新建，按 §3.4–3.6 |
| `Workflow.tsx` | `StepOutput` 按 §3.7 接入内联 AI 改写 |
| `draw_studio/workflows/copilot.py` | `SYSTEM` 加入 §4.5 的语调段与范例；`tool` 事件带 `op` |
| 终验脚本 | §5 的截图、动效帧、扫描与 trace |

`agentCopy.ts` 由本规格锁定。确实需要新文案时先在 `agentCopy.ts` 里加键，并在交付说明里列出新增的键和文字，终验时一并审。
