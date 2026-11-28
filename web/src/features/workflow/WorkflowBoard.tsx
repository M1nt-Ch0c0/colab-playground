import { ChevronDown, ChevronRight, CircleAlert, Clapperboard, Copy, Film, GitBranch, ImageIcon, Images, MessageSquare, Minus, Pencil, Plus, ScanSearch, Trash2, WandSparkles } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useId, useRef, useState, type PointerEvent } from 'react'
import { media } from '../../api/client'
import type { WfDef, WfRun, WfStep } from '../../api/types'
import { clamp, copyText, cx } from '../../lib/util'
import { useStore } from '../../store/store'
import { expand, instant } from '../../ui/motion'
import { AGENT_COPY as C } from './agentCopy'
import { WorkflowAgent, type AgentBinding } from './WorkflowAgent'

const ICONS = {
  asset_input: Images, llm_script: Clapperboard, web_asset_fetch: ScanSearch, image_gen: ImageIcon,
  h3_prompt: WandSparkles, video_gen: Film, video_stitch: Clapperboard,
}
const STATE_DOT = { running: 'busy', done: 'ok', error: 'bad' } as const
const WIDTH = 166, HEIGHT = 68
type Point = { x: number; y: number }

function upstream(step: WfStep): string[] {
  const keys = ['scenes_from', 'keyframe_from', 'prompts_from', 'clips_from', 'video_from', 'ref_sources', 'extra_ref_sources']
  return [...new Set(keys.flatMap(key => step.config[key]).filter((id): id is string => typeof id === 'string' && !!id))]
}

function layout(steps: WfStep[]) {
  const points = new Map<string, Point>(), levels = new Map<string, number>(), rows = new Map<number, number>()
  for (const step of steps) {
    const parents = upstream(step).filter(id => levels.has(id))
    const level = parents.length ? 1 + Math.max(...parents.map(id => levels.get(id)!)) : 0
    const row = rows.get(level) ?? 0
    levels.set(step.id, level)
    rows.set(level, row + 1)
    points.set(step.id, step.position ?? { x: 24 + level * (WIDTH + 60), y: 24 + row * (HEIGHT + 32) })
  }
  return points
}

export function useWorkflowSelection(runId?: string) {
  const params = new URLSearchParams(location.search)
  const linked = !!runId && params.get('workflow') === runId
  const [selected, select] = useState(linked ? params.get('node') || '' : '')
  const [agentOpen, setAgentOpen] = useState(linked && params.get('assistant') === 'open')
  function ask(id: string) {
    select(id)
    setAgentOpen(true)
  }
  return { selected, select, agentOpen, setAgentOpen, ask }
}

type VariableKind = keyof typeof C.vars.types
const variableKinds = ['string', 'number', 'boolean'] as const
const heightStates = { hidden: { height: 0, opacity: 0 }, shown: { height: 'auto', opacity: 1 } }

function Variables({ id, workflow, change, disabled }: { id: string; workflow: WfDef; change: (wf: WfDef) => void; disabled: boolean }) {
  const reduce = useReducedMotion()
  const toast = useStore(s => s.toast)
  const vars = workflow.variables ?? {}
  const [editing, setEditing] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [kind, setKind] = useState<VariableKind>('string')
  const [raw, setRaw] = useState('')
  const [error, setError] = useState('')

  function edit(key: string) {
    setEditing(key)
    setName(key)
    setRaw(key ? String(vars[key]) : '')
    setKind(key ? typeof vars[key] as VariableKind : 'string')
    setError('')
  }

  function save() {
    const key = name.trim()
    if (!/^[A-Za-z_][A-Za-z0-9_]{0,47}$/.test(key)) return setError(C.vars.errors.name)
    if (key !== editing && Object.hasOwn(vars, key)) return setError(C.vars.errors.taken)
    if (!editing && Object.keys(vars).length >= 32) return setError(C.vars.errors.tooMany)
    if (workflow.steps.some(step => step.id === 'vars')) return setError(C.vars.errors.reserved)
    if (kind === 'number' && (!raw.trim() || !Number.isFinite(Number(raw)))) return setError(C.vars.errors.number)
    const value = kind === 'boolean' ? raw === 'true' : kind === 'number' ? Number(raw) : raw
    change({ ...workflow, variables: { ...vars, [key]: value } })
    setEditing(null)
  }

  function remove(key: string) {
    const next = { ...vars }
    delete next[key]
    change({ ...workflow, variables: next })
    if (editing === key) setEditing(null)
  }

  async function copy(key: string) {
    const copied = await copyText('{{vars.' + key + '}}')
    toast(copied ? C.toast.refCopied : C.toast.copyFailed, copied ? 'ok' : 'err')
  }

  const transition = reduce ? instant : expand
  return <motion.section id={id} className="wf-variables" aria-label={C.vars.title}
    initial={reduce ? false : heightStates.hidden} animate={heightStates.shown}
    exit={reduce ? { opacity: 0 } : heightStates.hidden} transition={transition}>
    <div className="var-inner">
      <AnimatePresence initial={false}>
        {Object.entries(vars).map(([key, value]) => <motion.div key={key} className="var-row"
          initial={reduce ? false : heightStates.hidden} animate={heightStates.shown}
          exit={reduce ? { opacity: 0 } : heightStates.hidden} transition={transition}>
          <div className="var-row-content">
            <span className="mono var-name" data-user-content>{key}</span>
            <span className="var-value" data-user-content>{typeof value === 'boolean' ? C.vars.booleanValues[value ? 'true' : 'false'] : String(value)}</span>
            <button className="iconbtn sm" aria-label={C.vars.copyRef(key)} onClick={() => void copy(key)}><Copy size={13} /></button>
            <button className="iconbtn sm" aria-label={C.vars.edit(key)} disabled={disabled} onClick={() => edit(key)}><Pencil size={13} /></button>
            <button className="iconbtn sm" aria-label={C.vars.remove(key)} disabled={disabled} onClick={() => remove(key)}><Trash2 size={13} /></button>
          </div>
        </motion.div>)}
      </AnimatePresence>
      {Object.keys(vars).length === 0 && <span className="var-empty">{C.vars.empty}</span>}
      <button className="btn sm ghost" disabled={disabled} onClick={() => edit('')}><Plus size={13} />{C.vars.add}</button>
      {editing !== null && !disabled && <form className="var-form" onSubmit={event => { event.preventDefault(); save() }}>
        <input aria-label={C.vars.nameLabel} placeholder={C.vars.namePlaceholder} maxLength={48} value={name}
          disabled={!!editing} onChange={event => setName(event.target.value)} />
        <select aria-label={C.vars.typeLabel} value={kind} onChange={event => {
          const next = event.target.value as VariableKind
          setKind(next)
          if (next === 'boolean') setRaw('true')
        }}>
          {variableKinds.map(value => <option key={value} value={value}>{C.vars.types[value]}</option>)}
        </select>
        {kind === 'boolean' ? <select aria-label={C.vars.valueLabel} value={raw === 'true' ? 'true' : 'false'} onChange={event => setRaw(event.target.value)}>
          <option value="true">{C.vars.booleanValues.true}</option><option value="false">{C.vars.booleanValues.false}</option>
        </select> : <input aria-label={C.vars.valueLabel} placeholder={C.vars.valuePlaceholder} maxLength={2000} value={raw}
          inputMode={kind === 'number' ? 'decimal' : undefined} onChange={event => setRaw(event.target.value)} />}
        <button className="btn sm ghost" type="button" onClick={() => setEditing(null)}>{C.vars.cancel}</button>
        <button className="btn sm primary" type="submit">{C.vars.save}</button>
        {error && <span className="var-error" role="alert"><CircleAlert size={14} />{error}</span>}
      </form>}
    </div>
  </motion.section>
}

function nodeName(step: WfStep) {
  return step.name.replace(/^\d+[.、]\s*/, '')
}

function metadata(step: WfStep) {
  const { scene_count, width, height, target_width, target_height, num_frames } = step.config
  if (step.type === 'llm_script') return C.board.nodeDetail.scenes(scene_count ?? 3)
  if (width && height) return C.board.nodeDetail.size(width, height)
  if (target_width && target_height) return C.board.nodeDetail.size(target_width, target_height)
  if (num_frames) return C.operation.frames(num_frames)
  return ''
}

const OFFSETS: Record<string, Point> = {
  ArrowUp: { x: 0, y: -12 }, ArrowDown: { x: 0, y: 12 },
  ArrowLeft: { x: -12, y: 0 }, ArrowRight: { x: 12, y: 0 },
}
const coordinate = (value: number) => Math.round(clamp(value, 0, 8000))

export function WorkflowBoard({ binding, change, selection, run }: {
  binding: AgentBinding; change: (wf: WfDef) => void; selection: ReturnType<typeof useWorkflowSelection>; run?: WfRun
}) {
  const wf = binding.editor.workflow
  const disabled = !!binding.locked || binding.status === 'running'
  const { selected, select, ask } = selection
  const current = wf.steps.find(step => step.id === selected)
  const [showVars, setShowVars] = useState(false)
  const [scale, setScale] = useState(1)
  const [preview, setPreview] = useState<{ id: string; point: Point } | null>(null)
  const variablesId = useId()
  const drag = useRef<{ id: string; start: Point; origin: Point; next: Point | null } | null>(null)
  const frame = useRef(0)
  useEffect(() => () => cancelAnimationFrame(frame.current), [])
  const points = layout(wf.steps)
  if (preview) points.set(preview.id, preview.point)
  const width = Math.max(480, ...Array.from(points.values(), point => point.x + WIDTH + 40))
  const height = Math.max(200, ...Array.from(points.values(), point => point.y + HEIGHT + 24))
  const rounds = useStore(s => s.rounds)
  const refs = wf.steps.filter(step => step.type === 'asset_input').flatMap(step => {
    const ids: string[] = Array.isArray(step.config.round_ids) ? step.config.round_ids : []
    const files: string[] = run && Array.isArray(step.config.asset_files) ? step.config.asset_files : []
    return [
      ...ids.flatMap(id => {
        const round = rounds.find(item => item.id === id && item.kind === 'image')
        return round ? [{ step, src: media.thumb(round) }] : []
      }),
      ...files.map(file => ({ step, src: media.assetThumb(run!.id, file) })),
    ]
  }).slice(0, 8)

  const wires = wf.steps.flatMap((step, index) => {
    const prior = wf.steps.slice(0, index)
    return upstream(step).filter(id => prior.some(item => item.id === id)).map(id => ({
      from: id, to: step.id, selected: id === current?.id || step.id === current?.id,
    }))
  }).sort((a, b) => Number(a.selected) - Number(b.selected))

  function move(id: string, point: Point) {
    change({ ...wf, steps: wf.steps.map(step => step.id === id ? { ...step, position: point } : step) })
  }

  function inspect(id: string) {
    const header = document.getElementById('workflow-step-' + id)
    if (!header) return
    if (header.getAttribute('aria-expanded') !== 'true') header.click()
    header.scrollIntoView({ block: 'center' })
    header.focus({ preventScroll: true })
  }

  function pointerMove(event: PointerEvent, id: string) {
    const active = drag.current
    if (!active || active.id !== id) return
    const dx = (event.clientX - active.start.x) / scale
    const dy = (event.clientY - active.start.y) / scale
    if (!active.next && Math.abs(dx) + Math.abs(dy) < 4) return
    active.next = { x: coordinate(active.origin.x + dx), y: coordinate(active.origin.y + dy) }
    if (frame.current) return
    frame.current = requestAnimationFrame(() => {
      frame.current = 0
      if (drag.current?.next) setPreview({ id: drag.current.id, point: drag.current.next })
    })
  }

  function finishDrag(save: boolean) {
    if (!drag.current) return
    const { id, next } = drag.current
    drag.current = null
    cancelAnimationFrame(frame.current)
    frame.current = 0
    setPreview(null)
    if (save && next && !disabled) move(id, next)
  }

  return <>
    <section className="graph-shell glass" aria-label={C.board.title}>
      <header className="graph-heading">
        <GitBranch size={16} /><h3>{C.board.title}</h3><span className="grow" />
        <button className="graph-vars" aria-expanded={showVars} aria-controls={variablesId} onClick={() => setShowVars(value => !value)}>
          {C.board.variables}<span className="tabular">{Object.keys(wf.variables ?? {}).length}</span><ChevronDown size={13} />
        </button>
        <div className="graph-zoom">
          <button className="iconbtn sm" aria-label={C.board.zoomOut} disabled={scale <= .5} onClick={() => setScale(value => value - .25)}><Minus size={14} /></button>
          <button className="graph-scale tabular" aria-label={C.board.zoomReset} onClick={() => setScale(1)}>{C.board.zoomValue(scale)}</button>
          <button className="iconbtn sm" aria-label={C.board.zoomIn} disabled={scale >= 1.5} onClick={() => setScale(value => value + .25)}><Plus size={14} /></button>
        </div>
      </header>
      <AnimatePresence initial={false}>
        {showVars && <Variables key="variables" id={variablesId} workflow={wf} change={change} disabled={disabled} />}
      </AnimatePresence>
      <div className="graph-viewport" tabIndex={0} aria-label={C.board.canvas}>
        <div className="graph-size" style={{ width: width * scale, height: height * scale }}>
          <div className="graph-plane" style={{ width, height, transform: 'scale(' + scale + ')' }}
            onClick={event => { if (event.target === event.currentTarget) select('') }}>
            <svg className="graph-wires" width={width} height={height} aria-hidden="true" data-selection={!!current}>
              {wires.map(wire => {
                const source = points.get(wire.from)!, target = points.get(wire.to)!
                const x = source.x + WIDTH, y = source.y + HEIGHT / 2, end = target.y + HEIGHT / 2
                const bend = Math.max(28, Math.abs(target.x - x) / 2)
                const path = ['M', x, y, 'C', x + bend, y, target.x - bend, end, target.x, end].join(' ')
                return <path key={wire.from + ':' + wire.to} className={wire.selected ? 'selected' : undefined} d={path} />
              })}
            </svg>
            {wf.steps.map((step, index) => {
              const point = points.get(step.id)!
              const Icon = ICONS[step.type]
              const name = nodeName(step)
              const status = run?.step_states[step.id]?.status
              const dot = status && status in STATE_DOT ? STATE_DOT[status as keyof typeof STATE_DOT] : null
              return <button type="button" key={step.id} className={cx('graph-node', !step.enabled && 'off')}
                data-step-id={step.id} data-dragging={preview?.id === step.id ? '' : undefined}
                aria-label={[C.board.selectNode(name), !step.enabled && C.board.nodeOff].filter(Boolean).join(' ')}
                aria-pressed={step.id === current?.id}
                style={{ left: point.x, top: point.y, width: WIDTH, height: HEIGHT }}
                onClick={() => select(step.id)} onDoubleClick={() => inspect(step.id)}
                onPointerDown={event => {
                  if (event.button !== 0 || disabled) return
                  select(step.id)
                  drag.current = { id: step.id, start: { x: event.clientX, y: event.clientY }, origin: point, next: null }
                  event.currentTarget.setPointerCapture(event.pointerId)
                }}
                onPointerMove={event => pointerMove(event, step.id)}
                onPointerUp={() => finishDrag(true)} onLostPointerCapture={() => finishDrag(false)}
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    select(step.id)
                    inspect(step.id)
                  }
                  const offset = OFFSETS[event.key]
                  if (!disabled && event.shiftKey && offset) {
                    event.preventDefault()
                    move(step.id, { x: coordinate(point.x + offset.x), y: coordinate(point.y + offset.y) })
                  }
                }}>
                <span className="graph-node-type"><Icon size={13} />{C.board.nodeTypes[step.type]}
                  {dot && <span className={cx('dot', dot)} aria-hidden="true" />}<span className="tabular">{index + 1}</span>
                </span>
                <b data-user-content>{name}</b><span className="graph-node-meta">{metadata(step)}</span>
              </button>
            })}
          </div>
        </div>
      </div>
      {refs.length > 0 && <div className="graph-refs" aria-label={C.board.refs}>
        {refs.map(({ step, src }, index) => <button key={step.id + ':' + index}
          aria-label={C.board.refAlt(nodeName(step))} onClick={() => select(step.id)}>
          <img src={src} alt="" />
        </button>)}
      </div>}
      <footer className="graph-footer">
        {current ? <>
          <span className="graph-selection" data-user-content>{nodeName(current)}</span>
          <button className="btn sm ghost" onClick={() => inspect(current.id)}>{C.board.editNode}<ChevronRight size={13} /></button>
          <button className="btn sm ghost" onClick={() => ask(current.id)}><MessageSquare size={13} />{C.board.askAgent}</button>
        </> : <span>{wf.steps.length ? C.board.hint : C.board.emptyHint}</span>}
      </footer>
    </section>
    <WorkflowAgent binding={binding} open={selection.agentOpen} setOpen={selection.setAgentOpen}
      selected={current?.id ?? ''} clearSelection={() => select('')} />
  </>
}
