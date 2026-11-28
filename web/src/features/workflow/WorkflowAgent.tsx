import { ArrowUp, ArrowUpDown, Check, ChevronRight, CircleAlert, MessageSquare, Minus, PanelRight, Play, Square, Workflow, X } from 'lucide-react'
import { animate, AnimatePresence, motion, useMotionValue, useReducedMotion } from 'motion/react'
import { useEffect, useId, useLayoutEffect, useRef, useState, type PointerEvent } from 'react'
import { createPortal } from 'react-dom'
import { api, ApiError } from '../../api/client'
import type { AgentPlugins as Inventory, AgentRunRequest, AgentTool, EditorSnapshot, Operation, Proposal, RunShotUpdate, RunStatus, SavedAgentExchange } from '../../api/types'
import { clamp, requestId } from '../../lib/util'
import { applyAssistantComposerPatch, assistantComposerContext, useStore } from '../../store/store'
import { fade, instant, quick, spring, springSmall } from '../../ui/motion'
import { Seg } from '../../ui/Overlay'
import { AgentPlugins } from './AgentPlugins'
import { AGENT_COPY as C, ERROR_ACTION_LABELS, errorCopy, toolLabel, type ErrorAction, type HarnessErrorCode } from './agentCopy'
import { ConflictBar } from './ConflictBar'
import { WorkflowProposal } from './ProposalCard'
import { OperationCard, operationActive, operationReconciling } from './OperationCard'

export interface AgentBinding {
  editor: EditorSnapshot
  runId?: string
  draftId?: string
  composerScope?: string
  workspace?: 'image' | 'video'
  status?: RunStatus
  locked?: boolean
  beforeSend?: () => Promise<boolean>
  apply: (next: EditorSnapshot, revision: string | null) => Promise<EditorSnapshot>
  refresh?: () => Promise<EditorSnapshot | void>
  onShotUpdate?: (update: RunShotUpdate, output?: Record<string, unknown>) => void
  openRun: (id: string) => void
  run: (request: AgentRunRequest) => void
}

interface Exchange extends Omit<SavedAgentExchange, 'state'> {
  state: 'working' | 'done' | 'error' | 'stopped' | 'stale'
  fresh?: boolean
  applied?: string
  action?: AgentRunRequest | null
  version?: string
  error?: { code?: HarnessErrorCode; runId?: string; unsaved?: boolean }
}

const chat = C.agent
const syncedPluginRev = new Map<string, number>()
const RECONCILE_BACKOFF = [1500, 3000, 6000, 12000] as const
const tabs = [{ id: 'chat', label: chat.tabs.chat }, { id: 'plugins', label: chat.tabs.plugins }] as const
type Tab = typeof tabs[number]['id']
type Dock = 'right' | 'float' | 'sheet'
type Point = { x: number; y: number }
const screenDock = (): Dock => innerWidth <= 760 ? 'sheet' : innerWidth < 1280 ? 'float' : 'right'
const version = ({ workflow, topic }: EditorSnapshot) =>
  JSON.stringify([topic, workflow.name, workflow.description, workflow.default_topic, workflow.variables ?? {}, workflow.steps])

function savedProposals(saved: Proposal[] | undefined, local: Proposal[] | undefined) {
  if (!local) return saved
  return local.map(proposal => {
    const match = saved?.find(item => item.proposal_id === proposal.proposal_id)
    if (!match || proposal.status === 'undone' || (match.status === 'pending' && proposal.status !== 'pending')) return proposal
    return match
  })
}

function turnHistory(rows: readonly Exchange[]) {
  const items: { role: 'user' | 'assistant'; text: string }[] = []
  for (const row of rows) {
    if (row.state !== 'done') continue
    const user = row.user.trim().slice(0, 3000)
    if (user) items.push({ role: 'user', text: user })
    const answer = row.answer.trim().slice(0, 3000)
    if (answer) items.push({ role: 'assistant', text: answer })
  }
  return items.slice(-12)
}

function mergeHistory(saved: SavedAgentExchange[], current: Exchange[]): Exchange[] {
  const savedIds = new Set(saved.map(row => row.id))
  const firstSaved = current.findIndex(row => savedIds.has(row.id))
  const local = new Map(current.map(row => [row.id, row]))
  const before = new Map<string, Exchange[]>()
  const tail: Exchange[] = []
  let pending: Exchange[] = []
  for (const [index, row] of current.entries()) {
    if (savedIds.has(row.id)) {
      if (pending.length) {
        before.set(row.id, pending)
        pending = []
      }
    } else if (!(saved.length >= 24 && (firstSaved < 0 || index < firstSaved) && row.state === 'done')) {
      pending.push(row)
    }
  }
  tail.push(...pending)
  const ordered: Exchange[] = []
  for (const row of saved) {
    const prior = before.get(row.id)
    if (prior) ordered.push(...prior)
    const own = local.get(row.id)
    const proposals = savedProposals(row.proposals, own?.proposals)
    if (own && (own.state === 'stale' || own.state === 'error' || own.state === 'stopped')) {
      ordered.push({ ...own, proposals })
    } else {
      ordered.push({
        id: row.id, user: row.user, answer: row.answer, state: row.state, tools: row.tools.filter(tool => typeof tool.name === 'string'),
        applied: own?.applied, action: own?.action, version: own?.version, proposals, operation_id: row.operation_id ?? own?.operation_id,
      })
    }
  }
  return [...ordered, ...tail]
}

function ToolBadges({ tools, fresh }: { tools: AgentTool[]; fresh: boolean }) {
  const reduce = useReducedMotion()
  const [expanded, setExpanded] = useState(false)
  const badges: (AgentTool & { count: number })[] = []
  for (const tool of tools) {
    const previous = badges.at(-1)
    if (previous?.name === tool.name && previous.op === tool.op) {
      previous.count++
      previous.ok = previous.ok === false || tool.ok === false ? false
        : previous.ok === null || tool.ok === null ? null : true
    } else {
      badges.push({ ...tool, count: 1 })
    }
  }
  return <div className="agent-tools">
    {(expanded ? badges : badges.slice(0, 4)).map(({ name, op, ok, call_id, count }, index) => {
      const text = toolLabel(name, typeof op === 'string' ? op : undefined)
      return <motion.span key={call_id ?? index} className="tag agent-tool"
        initial={reduce || !fresh ? false : { opacity: 0, scale: .85, x: -4 }}
        animate={{ opacity: 1, scale: 1, x: 0 }} transition={reduce ? instant : { ...springSmall, delay: Math.min(index, 4) * .04 }}>
        <span className="agent-tool-icon">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span key={String(ok)} initial={reduce ? false : { opacity: 0, scale: .6 }}
              animate={{ opacity: 1, scale: 1 }} exit={reduce ? { opacity: 0 } : { opacity: 0, scale: .6 }}
              transition={reduce ? instant : springSmall}>
              {ok === null ? <span className="spinner" /> : ok ? <Check size={12} className="tool-ok" />
                : <CircleAlert size={12} className="tool-failed" aria-label={chat.tools.failedAria(text)} role="img" />}
            </motion.span>
          </AnimatePresence>
        </span>
        {text}{count > 1 && <span className="tabular">{chat.tools.repeat(count)}</span>}
      </motion.span>
    })}
    {badges.length > 4 && <button className="tag agent-more" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
      {expanded ? chat.collapse : chat.tools.more(badges.length - 4)}
    </button>}
  </div>
}

export function WorkflowAgent({ binding, selected, selectedShot, clearSelection, open, setOpen }: {
  binding: AgentBinding; selected: string; selectedShot?: { id: string; n: number };
  clearSelection: () => void; open: boolean; setOpen: (open: boolean) => void
}) {
  const reduce = useReducedMotion()
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const exchangeRef = useRef(exchanges)
  exchangeRef.current = exchanges
  const [operations, setOperations] = useState<Operation[]>([])
  const operationRef = useRef<Operation[]>([])
  const operationVersion = useRef(0)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [unread, setUnread] = useState(false)
  const [tab, setTab] = useState<Tab>('chat')
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [screen, setScreen] = useState(screenDock)
  const [free, setFree] = useState(false)
  const [sheetTop, setSheetTop] = useState(false)
  const [jump, setJump] = useState(false)
  const dock = screen === 'sheet' ? 'sheet' : free ? 'free' : screen
  const [x, y] = [useMotionValue(0), useMotionValue(0)]
  const [originX, originY] = [useMotionValue(1), useMotionValue(1)]
  const moveAnimation = useRef<{ stop: () => void } | null>(null)
  const pendingJump = useRef<Point | null>(null)
  const drag = useRef<{ start: Point; translation: Point; moved: boolean } | null>(null)
  const panel = useRef<HTMLElement>(null)
  const launcher = useRef<HTMLButtonElement>(null)
  const launchRect = useRef<DOMRect | null>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const log = useRef<HTMLDivElement>(null)
  const nearBottom = useRef(true)
  const latest = useRef(binding)
  latest.current = binding
  const shown = useRef({ open, tab })
  shown.current = { open, tab }
  const request = useRef<{ controller: AbortController; id: string; started: boolean } | null>(null)
  const key = binding.runId || binding.composerScope || (binding.draftId ? 'wr_' + binding.draftId : '')
  const step = binding.editor.workflow.steps.find(item => item.id === selected)
  const titleId = useId()
  const settings = useStore(s => s.openSheet)
  const toast = useStore(s => s.toast)
  const colabAuthed = useStore(s => s.status?.colab.authed)
  const bumpPluginRev = useStore(s => s.bumpAgentPluginRev)
  const locked = !!binding.locked

  function rememberOperations(incoming: Operation[], polled = false) {
    const previous = operationRef.current
    if (polled && !shown.current.open) {
      for (const op of incoming) {
        const before = previous.find(item => item.operation_id === op.operation_id)
        if (!before || !operationActive(before.state)) continue
        if (op.state === 'done') toast(C.toast.operationDone(op.done, op.kind), 'ok')
        else if (op.state === 'partial' || op.state === 'failed') {
          const failed = op.items.filter(item => item.state === 'failed').length
          if (failed) toast(C.toast.operationFailed(failed), 'err')
        }
      }
    }
    const next = polled ? incoming : [
      ...incoming, ...previous.filter(item => !incoming.some(op => op.operation_id === item.operation_id)),
    ]
    if (JSON.stringify(next) === JSON.stringify(previous)) return
    operationVersion.current++
    operationRef.current = next
    setOperations(next)
  }

  const [syncStalled, setSyncStalled] = useState(false)
  const [syncNonce, setSyncNonce] = useState(0)
  const watching = operations.some(op => operationActive(op.state))
  const reconciling = open && !watching && operations.some(operationReconciling)
  useEffect(() => {
    if (!key) return
    let active = true
    let timer = 0
    let reconcileAttempt = 0
    setSyncStalled(false)
    async function poll() {
      const version = operationVersion.current
      try {
        const result = await api.wf.operations(key)
        if (active && version === operationVersion.current) rememberOperations(result.operations, true)
      } catch { /* The next poll will reload the ledger. */ }
      if (!active) return
      if (operationRef.current.some(op => operationActive(op.state))) {
        reconcileAttempt = 0
        setSyncStalled(false)
        timer = window.setTimeout(poll, 1200)
      } else if (open && operationRef.current.some(operationReconciling)) {
        const delay = RECONCILE_BACKOFF[reconcileAttempt++]
        if (delay !== undefined) timer = window.setTimeout(poll, delay)
        else setSyncStalled(true)
      } else {
        setSyncStalled(false)
      }
    }
    void poll()
    return () => { active = false; clearTimeout(timer) }
  }, [key, open, watching, reconciling, colabAuthed, syncNonce]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open || !key) return
    let active = true
    api.wf.conversation(key).then(({ exchanges: saved }) => {
      if (active) setExchanges(current => mergeHistory(saved, current))
    }).catch(() => { if (active) toast(C.toast.historyFailed, 'err') })
    return () => { active = false }
  }, [key, open, toast])

  useEffect(() => {
    if (!open) return
    let active = true
    setLoadFailed(false)
    api.wf.plugins().then(data => { if (active) setInventory(data) }).catch(() => { if (active) setLoadFailed(true) })
    return () => { active = false }
  }, [open, loadAttempt])

  useEffect(() => () => { request.current?.controller.abort() }, [])
  useEffect(() => {
    function resize() {
      moveAnimation.current?.stop()
      moveAnimation.current = null
      pendingJump.current = null
      drag.current = null
      x.jump(0)
      y.jump(0)
      setScreen(screenDock())
      setFree(false)
      setSheetTop(false)
    }
    window.addEventListener('resize', resize)
    return () => { window.removeEventListener('resize', resize); moveAnimation.current?.stop() }
  }, [x, y])

  function setOrigin(rect: DOMRect | null) {
    const element = panel.current
    if (!element || !rect) return
    originX.set((rect.left + rect.width / 2 - element.offsetLeft - x.get()) / element.offsetWidth)
    originY.set((rect.top + rect.height / 2 - element.offsetTop - y.get()) / element.offsetHeight)
  }

  useLayoutEffect(() => {
    if (open) setOrigin(launchRect.current ?? launcher.current?.getBoundingClientRect() ?? null)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open || tab !== 'chat') return
    nearBottom.current = true
    setJump(false)
    setUnread(false)
    if (log.current) log.current.scrollTop = log.current.scrollHeight
    if (matchMedia('(pointer: fine)').matches) composer.current?.focus({ preventScroll: true })
  }, [open, tab])

  useEffect(() => {
    const element = log.current
    if (open && tab === 'chat' && element && nearBottom.current) {
      element.scrollTo({ top: element.scrollHeight, behavior: reduce ? 'auto' : 'smooth' })
    }
  }, [exchanges, operations, open, tab, reduce])

  function openPanel() {
    launchRect.current = launcher.current?.getBoundingClientRect() ?? null
    setOpen(true)
    setUnread(false)
  }

  function close() {
    setOrigin(launchRect.current)
    setExchanges(rows => rows.map(row => row.fresh ? { ...row, fresh: false } : row))
    setOpen(false)
    requestAnimationFrame(() => launcher.current?.focus({ preventScroll: true }))
  }

  function selectTab(next: Tab) {
    if (tab === next) return
    setExchanges(rows => rows.map(row => row.fresh ? { ...row, fresh: false } : row))
    if (next === 'chat') setUnread(false)
    setTab(next)
  }

  function inside(element: HTMLElement, point: Point) {
    return {
      x: clamp(point.x, 0, Math.max(0, innerWidth - element.offsetWidth)),
      y: clamp(point.y, 0, Math.max(0, innerHeight - element.offsetHeight)),
    }
  }

  useLayoutEffect(() => {
    const target = pendingJump.current
    if (!target) return
    pendingJump.current = null
    x.jump(target.x)
    y.jump(target.y)
  }, [free, x, y])

  function movePanel(point: Point, targetDock: 'free' | Dock) {
    const element = panel.current
    if (!element) return
    moveAnimation.current?.stop()
    moveAnimation.current = null
    const target = inside(element, point)
    const finish = () => {
      const nextFree = targetDock === 'free'
      const nextPoint = nextFree ? target : { x: 0, y: 0 }
      const wasFree = panel.current?.dataset.dock === 'free'
      if (nextFree === wasFree) {
        pendingJump.current = null
        x.jump(nextPoint.x)
        y.jump(nextPoint.y)
      } else {
        pendingJump.current = nextPoint
        setFree(nextFree)
      }
    }
    if (reduce) { finish(); return }
    element.setAttribute('data-animating', '')
    const horizontal = animate(x, target.x - element.offsetLeft, spring)
    const vertical = animate(y, target.y - element.offsetTop, spring)
    const control = { stop: () => {
      horizontal.stop()
      vertical.stop()
      element.removeAttribute('data-animating')
    } }
    moveAnimation.current = control
    void Promise.all([horizontal, vertical]).then(() => {
      if (moveAnimation.current !== control) return
      moveAnimation.current = null
      element.removeAttribute('data-animating')
      finish()
    })
  }

  function moveAside() {
    const element = panel.current
    if (!element) return
    if (screen === 'sheet') { setSheetTop(value => !value); return }
    const current = element.getBoundingClientRect()
    const gap = screen === 'right' ? 16 : 20
    const left = current.left + current.width / 2 > innerWidth / 2
    if (screen === 'right' && !left) { resetDock(); return }
    movePanel({ x: left ? gap : innerWidth - element.offsetWidth - gap, y: current.top }, 'free')
  }

  function resetDock() {
    const element = panel.current
    if (!element || screen === 'sheet' || (dock !== 'free' && !moveAnimation.current)) return
    const top = Number.parseFloat(getComputedStyle(element).getPropertyValue('--top')) || 0
    movePanel(screen === 'right'
      ? { x: innerWidth - element.offsetWidth - 16, y: top + 18 }
      : { x: innerWidth - element.offsetWidth - 20, y: innerHeight - element.offsetHeight - 20 }, screen)
  }

  function dragStart(event: PointerEvent<HTMLElement>) {
    if (screen === 'sheet' || event.button !== 0 || (event.target as Element).closest('button')) return
    moveAnimation.current?.stop()
    moveAnimation.current = null
    pendingJump.current = null
    drag.current = { start: { x: event.clientX, y: event.clientY }, translation: { x: x.get(), y: y.get() }, moved: false }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function dragMove(event: PointerEvent<HTMLElement>) {
    const active = drag.current, element = panel.current
    if (!active || !element) return
    const dx = event.clientX - active.start.x, dy = event.clientY - active.start.y
    if (!active.moved && Math.abs(dx) + Math.abs(dy) < 4) return
    active.moved = true
    const next = inside(element, { x: element.offsetLeft + active.translation.x + dx, y: element.offsetTop + active.translation.y + dy })
    x.set(next.x - element.offsetLeft)
    y.set(next.y - element.offsetTop)
  }

  function dragEnd() {
    const active = drag.current, element = panel.current
    drag.current = null
    if (!active?.moved || !element || screen === 'sheet') return
    const point = inside(element, { x: element.offsetLeft + x.get(), y: element.offsetTop + y.get() })
    x.jump(point.x)
    y.jump(point.y)
    setFree(true)
  }

  function amend(id: string, patch: Partial<Exchange>) {
    setExchanges(rows => rows.map(row => row.id === id ? { ...row, ...patch } : row))
  }

  function updateProposal(exchangeId: string, previousId: string, proposal?: Proposal) {
    setExchanges(rows => rows.map(row => {
      if (!row.proposals || (row.id !== exchangeId && proposal?.proposal_id !== previousId)) return row
      return { ...row, proposals: row.proposals.flatMap(item => item.proposal_id !== previousId ? [item] : proposal ? [proposal] : []) }
    }))
  }

  function fill(text: string) {
    if (latest.current.locked) return
    setInput(text)
    composer.current?.focus()
  }

  async function send(text: string, consumeDraft = false, restartWithPlugins = false) {
    const message = text.trim()
    if (!message || request.current || latest.current.locked) return
    const active = { controller: new AbortController(), id: requestId(), started: false }
    const { id, controller } = active
    request.current = active
    setBusy(true)
    if (consumeDraft) setInput('')
    setExchanges(rows => [...rows, { id, user: message, answer: '', state: 'working', tools: [], fresh: true }])
    let original: string | undefined
    try {
      if (latest.current.beforeSend && !(await latest.current.beforeSend())) {
        amend(id, { state: 'error', error: { code: 'busy', unsaved: true } })
        return
      }
      controller.signal.throwIfAborted()
      const base = latest.current
      if (base.locked) throw new ApiError(409, '', 'busy')
      original = version(base.editor)
      const pluginRev = useStore.getState().agentPluginRev
      const needsPluginReload = restartWithPlugins || (key ? (syncedPluginRev.get(key) ?? 0) < pluginRev : pluginRev > 0)
      const done = await api.wf.agentTurn({
        ...base.editor, selected_step: selected, selected_shot: selectedShot?.id,
        run_id: base.runId, draft_id: base.draftId, turn_id: id, message,
        history: turnHistory(exchangeRef.current),
        workspace: base.workspace, composer_scope: base.composerScope, composer: base.workspace ? assistantComposerContext() : undefined,
        reload_plugins: needsPluginReload,
      }, controller.signal, event => {
        if (event.type === 'started') active.started = true
        if (event.type === 'session' && key) syncedPluginRev.set(key, pluginRev)
        if (event.type === 'tool') {
          if (event.operations?.length) {
            rememberOperations(event.operations)
            amend(id, { operation_id: event.operations.at(-1)?.operation_id })
          }
          const { type: _, operations: _operations, composer_patch: _patch, ...tool } = event
          setExchanges(rows => rows.map(row => {
            if (row.id !== id) return row
            const index = tool.call_id ? row.tools.findIndex(item => item.call_id === tool.call_id) : -1
            const tools = index < 0 ? [...row.tools, tool] : row.tools.map((item, i) => i === index ? tool : item)
            return { ...row, tools }
          }))
        }
      })
      controller.signal.throwIfAborted()
      const proposals = done.proposals ?? []
      for (const proposal of proposals) updateProposal(id, proposal.proposal_id, proposal)
      const updates = done.run_updated ?? []
      for (const update of updates) latest.current.onShotUpdate?.(update)
      amend(id, { answer: done.message, proposals })
      if (done.operations?.length) {
        rememberOperations(done.operations)
        amend(id, { operation_id: done.operations.at(-1)?.operation_id })
      }
      if (done.refresh_library) {
        void useStore.getState().loadWf()
        void useStore.getState().loadRounds()
        void useStore.getState().refresh()
      }
      let composerUpdated = false
      if (done.composer_patch) {
        try {
          composerUpdated = await applyAssistantComposerPatch(done.composer_patch)
          if (!composerUpdated) toast(C.conflict.changed, 'err')
        } catch (err) {
          toast(errorCopy(err instanceof ApiError ? err.code : undefined).text, 'err')
        }
      }
      if (done.mask_editor && !useStore.getState().sheet) {
        const store = useStore.getState()
        await store.loadRounds()
        if (!useStore.getState().sheet) store.openSheet('mask', { id: done.mask_editor.source_id, maskId: done.mask_editor.mask_id })
      }
      const refresh = async () => done.refresh_run ? (await latest.current.refresh?.().catch(() => undefined)) : undefined
      let next = base.editor
      if (done.editor || done.run_request) {
        const current = latest.current
        if (current.locked || version(current.editor) !== original || current.status !== base.status) {
          await refresh()
          amend(id, { state: 'stale' })
          return
        }
        if (done.editor) next = await current.apply(done.editor, done.base_revision)
      }
      if (!done.editor) {
        const refreshed = await refresh()
        if (refreshed) next = refreshed
      }
      const stepChanged = next.workflow.steps.find(item => item.type === 'llm_script' &&
        base.editor.workflow.steps.some(previous => previous.id === item.id && previous.config.scene_count !== item.config.scene_count))
      const previous = base.editor.workflow.steps.find(item => item.id === stepChanged?.id)
      const numbers = [...new Set(updates.filter(update => update.run_id === base.runId)
        .flatMap(update => update.changes.map(change => change.n)))].sort((a, b) => a - b)
      const applied = previous && stepChanged
        ? chat.applied.sceneCount(previous.config.scene_count, stepChanged.config.scene_count)
        : done.editor ? chat.applied.workflow : numbers.length ? chat.applied.shots(numbers) : composerUpdated ? C.toast.applied : undefined
      amend(id, { state: 'done', applied, action: done.run_request, version: version(next) })
    } catch (failure) {
      const error = failure instanceof ApiError ? failure : undefined
      if (controller.signal.aborted || error?.code === 'turn_stopped') amend(id, { state: 'stopped' })
      else if (error?.code === 'revision_conflict') {
        const current = latest.current
        if (original === version(current.editor)) await current.refresh?.().catch(() => {})
        amend(id, { state: 'stale' })
      } else {
        const runId = error?.details?.run_id
        amend(id, { state: 'error', error: { code: error?.code, runId: typeof runId === 'string' ? runId : undefined } })
      }
    } finally {
      request.current = null
      setBusy(false)
      setStopping(false)
      if (!shown.current.open || shown.current.tab !== 'chat') setUnread(true)
    }
  }

  async function stop() {
    const active = request.current
    if (!active || stopping) return
    setStopping(true)
    if (key && active.started) {
      try {
        if ((await api.wf.stopTurn(key, active.id)).stopped) return
      } catch { /* A disconnected stream is cancelled by the server. */ }
    }
    active.controller.abort()
  }

  function errorAction(action: ErrorAction, item: Exchange) {
    if (action === 'edit') fill(item.user)
    if (action === 'retry' || action === 'regenerate') void send(item.user)
    if (action === 'openModelSettings') settings('settings', { focus: 'llm' })
    if (action === 'openCompute') settings('settings')
    if (action === 'openRun' && item.error?.runId) binding.openRun(item.error.runId)
  }

  const suggestions = binding.workspace ? chat.suggestions[binding.workspace]
    : !step ? chat.suggestions.workflow
    : step.type === 'llm_script' ? [chat.suggestions.sceneCount(step.config.scene_count === 5 ? 3 : 5), chat.suggestions.polish, chat.suggestions.step]
    : step.type === 'h3_prompt' ? [chat.suggestions.polish, chat.suggestions.step] : [chat.suggestions.step]
  const choices = !binding.workspace && inventory?.plugin.enabled ? [...suggestions.slice(0, 2), chat.suggestions.timing] : suggestions
  const emptyHeading = binding.workspace ? chat.empty[binding.workspace] : step ? chat.empty.step : chat.empty.workflow
  const activeVersion = version(binding.editor)
  const operationOwners = new Map(exchanges.flatMap(item => item.operation_id ? [[item.operation_id, item.id] as const] : []))
  const panelTransition = reduce ? instant : { ...spring, opacity: fade, scale: springSmall }
  return createPortal(<AnimatePresence initial={false}>
    {!open ? <motion.button key="launch" ref={launcher} className="agent-launch glass" aria-haspopup="dialog" aria-expanded={false}
      data-composer={binding.workspace}
      aria-label={busy ? chat.launcherBusy : unread ? chat.launcherUnread : undefined}
      initial={reduce ? false : { opacity: 0, scale: .9 }} animate={{ opacity: 1, scale: 1 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, scale: .9, transition: quick }}
      transition={reduce ? instant : { ...springSmall, delay: .06 }} onClick={openPanel}>
      <MessageSquare size={17} /><span>{chat.launcher}</span>
      {busy ? <span className="dot busy" /> : unread && <span className="badge-dot" />}
    </motion.button> : <motion.section key="panel" ref={panel} className="workflow-agent glass" role="dialog" aria-modal={false}
      aria-labelledby={titleId} data-dock={dock} data-sheet-top={dock === 'sheet' && sheetTop ? '' : undefined}
      style={dock === 'sheet' ? undefined : { x, y, originX, originY }}
      initial={reduce ? false : dock === 'sheet' ? { opacity: 0, y: 24 } : { opacity: 0, scale: .94 }}
      animate={dock === 'sheet' ? { opacity: 1, y: 0 } : { opacity: 1, scale: 1 }}
      exit={reduce ? { opacity: 0 } : dock === 'sheet' ? { opacity: 0, y: 16 } : { opacity: 0, scale: .96 }}
      transition={panelTransition}
      onAnimationStart={() => { panel.current?.setAttribute('data-animating', '') }}
      onAnimationComplete={() => { panel.current?.removeAttribute('data-animating') }}
      onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close() } }}>
      <header className="agent-head" onPointerDown={dragStart} onPointerMove={dragMove} onPointerUp={dragEnd} onLostPointerCapture={dragEnd}
        onDoubleClick={event => { if (!(event.target as Element).closest('button')) resetDock() }}>
        <h2 id={titleId}>{chat.title}</h2>
        <Seg value={tab} onChange={selectTab} options={[...tabs]} ariaLabel={chat.tabs.aria} /><span className="grow" />
        <button className="iconbtn sm" aria-label={dock === 'sheet' ? sheetTop ? chat.moveDown : chat.moveUp : chat.moveAside} onClick={moveAside}>
          {dock === 'sheet' ? <ArrowUpDown size={16} /> : <PanelRight size={16} />}
        </button>
        <button className="iconbtn sm" aria-label={chat.collapse} onClick={close}><Minus size={17} /></button>
      </header>
      <motion.div key={tab} className="agent-tab" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}
        transition={reduce ? instant : quick}>
        {tab === 'plugins' ? <AgentPlugins data={inventory} loadFailed={loadFailed} retry={() => setLoadAttempt(value => value + 1)}
          disabled={busy || locked} changed={data => { setInventory(data); bumpPluginRev() }}
          tryTiming={() => { selectTab('chat'); void send(chat.suggestions.timing.prompt, false, true) }} /> : <>
          <div className="agent-context" aria-label={chat.context.aria}>
            <Workflow size={14} /><span data-user-content>{binding.editor.workflow.name}</span>
            {step && <><ChevronRight size={12} /><b data-user-content>{step.name.replace(/^\d+[.、]\s*/, '')}</b>
              {selectedShot && <><ChevronRight size={12} /><span>{chat.context.shot(selectedShot.n)}</span></>}
              <button className="iconbtn sm" aria-label={chat.context.clear} onClick={clearSelection}><X size={13} /></button>
            </>}
          </div>
          <div className="agent-history">
            <div ref={log} className="agent-log" role="log" aria-live="polite" aria-label={chat.status.historyAria}
              onScroll={event => {
                const element = event.currentTarget
                nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight <= 48
                setJump(!nearBottom.current)
              }}>
              {!exchanges.length && !operations.length && <div className="agent-empty">
                <h3>{emptyHeading}</h3>
                {choices.map(item => <button key={item.label} disabled={locked} onClick={() => fill(item.prompt)}>
                  {item.label}<ChevronRight size={14} />
                </button>)}
              </div>}
              {exchanges.map(item => {
                const fresh = item.fresh && !reduce
                const info = errorCopy(item.error?.code)
                const actions: ErrorAction[] = info.action && info.action !== 'edit' ? [info.action, 'edit'] : ['edit']
                const action = item.action
                const operation = operationOwners.get(item.operation_id ?? '') === item.id
                  ? operations.find(op => op.operation_id === item.operation_id) : undefined
                const target = action?.step_id && binding.editor.workflow.steps.find(node => node.id === action.step_id && node.enabled)
                return <div key={item.id} className="agent-exchange">
                  <motion.p className="agent-user" data-user-content style={{ originX: 1, originY: 1, whiteSpace: 'pre-wrap' }}
                    initial={fresh ? { opacity: 0, y: 8, scale: .98 } : false} animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={panelTransition}>{item.user}</motion.p>
                  {!!item.tools.length && <ToolBadges tools={item.tools} fresh={!!fresh} />}
                  {item.answer && <motion.p className="agent-answer" data-user-content="answer" style={{ whiteSpace: 'pre-wrap' }}
                    initial={fresh ? { opacity: 0, y: 4 } : false} animate={{ opacity: 1, y: 0 }}
                    transition={reduce ? instant : fade}>{item.answer}</motion.p>}
                  {item.applied && <motion.span className="tag ok agent-applied" initial={fresh ? { opacity: 0, scale: .9 } : false}
                    animate={{ opacity: 1, scale: 1 }} transition={reduce ? instant : { ...springSmall, delay: .05 }}>
                    <Check size={12} />{item.applied}
                  </motion.span>}
                  {item.proposals?.slice(-2).map(proposal => <WorkflowProposal key={proposal.proposal_id} proposal={proposal}
                    variant="panel" animateEntry={!!item.fresh} disabled={locked || busy || binding.status === 'running'}
                    beforeWrite={() => latest.current.beforeSend?.() ?? Promise.resolve(true)}
                    onUpdate={(update, output) => latest.current.onShotUpdate?.(update, output)}
                    onChange={next => updateProposal(item.id, proposal.proposal_id, next)}
                    onRegenerateComposer={() => void send(proposal.target.instruction)}
                    onDismiss={() => updateProposal(item.id, proposal.proposal_id)} />)}
                  {operation && <OperationCard key={operation.operation_id} operation={operation}
                    update={next => rememberOperations([next])} animateEntry={!!item.fresh} disabled={locked}
                    reconciling={!syncStalled} onRefresh={() => setSyncNonce(n => n + 1)} />}
                  <AnimatePresence initial={false}>
                    {item.state === 'stale' && <ConflictBar key="stale" conflict={{ kind: 'stale' }} disabled={locked || busy}
                      onRegenerate={() => { amend(item.id, { state: 'done' }); void send(item.user) }}
                      onKeep={() => amend(item.id, { state: 'done' })} />}
                  </AnimatePresence>
                  {item.state === 'error' && <div className="agent-error" role="alert">
                    <CircleAlert size={14} /><span>{item.error?.unsaved ? chat.unsaved : info.text}</span>
                    <div className="agent-links">{actions.map(action => <button key={action} className="mini-link"
                      disabled={locked || (busy && (action === 'retry' || action === 'regenerate'))}
                      onClick={() => errorAction(action, item)}>{ERROR_ACTION_LABELS[action]}</button>)}</div>
                  </div>}
                  {item.state === 'working' && <motion.span className="agent-working"
                    initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}
                    transition={reduce ? instant : { ...fade, delay: .25 }}>
                    <span className="spinner" />{stopping ? chat.status.stopping : chat.status.working}
                  </motion.span>}
                  {item.state === 'stopped' && <span className="agent-stopped">{chat.status.stopped}</span>}
                  {action && item.version === activeVersion && (!action.step_id || target) && binding.status !== 'running' &&
                    <button className="btn sm" disabled={busy || locked} onClick={() => {
                      binding.run(action)
                      amend(item.id, { action: null })
                    }}><Play size={13} />
                      {target ? (action.single_step ? chat.run.step : chat.run.from)(target.name.replace(/^\d+[.、]\s*/, ''))
                        : binding.status === 'paused' ? chat.run.resume : chat.run.start}
                    </button>}
                </div>
              })}
              {operations.filter(op => !operationOwners.has(op.operation_id)).slice().reverse().map(op =>
                <div className="agent-exchange" key={op.operation_id}>
                  <OperationCard operation={op} update={next => rememberOperations([next])} animateEntry={false} disabled={locked}
                    reconciling={!syncStalled} onRefresh={() => setSyncNonce(n => n + 1)} />
                </div>)}
            </div>
            <AnimatePresence>
              {jump && <motion.button className="chip agent-jump" initial={reduce ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }} exit={reduce ? { opacity: 0 } : { opacity: 0, y: 6 }}
                transition={reduce ? instant : springSmall} onClick={() => {
                  const element = log.current
                  if (element) element.scrollTo({ top: element.scrollHeight, behavior: reduce ? 'auto' : 'smooth' })
                }}>{chat.status.jumpLatest}</motion.button>}
            </AnimatePresence>
          </div>
          <form className="agent-compose" onSubmit={event => { event.preventDefault(); void send(input, true) }}>
            <textarea ref={composer} rows={2} maxLength={4000} value={input} aria-label={chat.composer.aria}
              disabled={locked} placeholder={step ? chat.composer.placeholderStep : chat.composer.placeholder}
              onChange={event => setInput(event.target.value)} onKeyDown={event => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault()
                  void send(input, true)
                }
              }} />
            {busy ? <button type="button" className="agent-send" aria-label={chat.composer.stop} disabled={stopping}
              onClick={() => void stop()}><Square size={14} /></button> : <button type="submit" className="agent-send"
              aria-label={chat.composer.send} disabled={locked || !input.trim()}><ArrowUp size={17} /></button>}
          </form>
        </>}
      </motion.div>
    </motion.section>}
  </AnimatePresence>, document.body)
}
