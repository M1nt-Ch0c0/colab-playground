import { Braces, Check, ChevronRight, Clapperboard, FileImage, Film, GitBranch, Image, Images, Minus, Pencil, Plus, ScanSearch, Trash2, WandSparkles } from 'lucide-react'
import { useRef, useState } from 'react'
import type { WfDef, WfStep } from '../../api/types'
import { useStore } from '../../store/store'

const NODE_TYPES = {
  llm_script: { icon: Clapperboard, label: '分镜' }, image_gen: { icon: Image, label: '关键帧' },
  asset_input: { icon: Images, label: '素材' }, web_asset_fetch: { icon: ScanSearch, label: '参考图' },
  h3_prompt: { icon: WandSparkles, label: '提示词' }, video_gen: { icon: Film, label: '视频' },
  video_stitch: { icon: Clapperboard, label: '剪辑' },
}
type Point = { x: number; y: number }
const W = 166, H = 68
function upstream(step: WfStep) {
  const config = step.config
  return [...new Set(['scenes_from', 'keyframe_from', 'prompts_from', 'clips_from', 'ref_sources', 'extra_ref_sources']
    .flatMap(k => Array.isArray(config[k]) ? config[k] : [config[k]]).filter((id): id is string => typeof id === 'string' && !!id))]
}

function layout(steps: WfStep[]) {
  const points = new Map<string, Point>(), levels = new Map<string, number>(), rows = new Map<number, number>()
  for (const step of steps) {
    const parents = upstream(step).filter(id => levels.has(id))
    const level = parents.length ? 1 + Math.max(...parents.map(id => levels.get(id)!)) : 0
    const row = rows.get(level) || 0
    levels.set(step.id, level)
    rows.set(level, row + 1)
    points.set(step.id, step.position || { x: 24 + level * (W + 60), y: 24 + row * (H + 32) })
  }
  return points
}

function Variables({ wf, change, disabled }: { wf: WfDef; change: (w: WfDef) => void; disabled: boolean }) {
  const vars = wf.variables || {}
  const [editing, setEditing] = useState<string | null>(null)
  const [key, setKey] = useState(''), [raw, setRaw] = useState('')
  const [type, setType] = useState('string'), [error, setError] = useState('')
  function edit(name: string) {
    setEditing(name); setKey(name); setRaw(String(vars[name] ?? ''))
    setType(name ? typeof vars[name] : 'string'); setError('')
  }
  function save() {
    const name = key.trim()
    if (!/^[A-Za-z_][A-Za-z0-9_]{0,47}$/.test(name)) { setError('名称以英文字母或下划线开头，可含数字，最多 48 个字符'); return }
    if (name !== editing && Object.hasOwn(vars, name)) { setError('这个变量名已存在'); return }
    if (!editing && Object.keys(vars).length >= 32) { setError('最多可定义 32 个变量'); return }
    if (wf.steps.some(s => s.id === 'vars')) { setError('当前已有 ID 为 vars 的步骤，占用了变量名称空间'); return }
    if (type === 'number' && (!raw.trim() || !Number.isFinite(Number(raw)))) { setError('请输入有效数字'); return }
    const value = type === 'boolean' ? raw === 'true' : type === 'number' ? Number(raw) : raw
    change({ ...wf, variables: { ...vars, [name]: value } })
    setEditing(null)
  }
  return <section className="wf-variables" aria-label="工作流变量">
    <div className="var-caption"><b>工作流变量</b><small>在提示词中用 <code>{'{{vars.name}}'}</code> 引用</small>
      <button className="iconbtn sm" aria-label="添加变量" disabled={disabled} onClick={() => edit('')}><Plus size={15} /></button></div>
    {Object.entries(vars).map(([name, value]) => <div className="var-row" key={name}>
      <code>{name}</code><span>{String(value)}</span><button className="iconbtn sm" disabled={disabled} aria-label={'编辑变量 ' + name} onClick={() => edit(name)}><Pencil size={13} /></button>
      <button className="iconbtn sm" disabled={disabled} aria-label={'删除变量 ' + name} onClick={() => {
        const next = { ...vars }; delete next[name]; change({ ...wf, variables: next }); if (editing === name) setEditing(null)
      }}><Trash2 size={13} /></button></div>)}
    {editing !== null && !disabled && <form className="var-form" onSubmit={e => { e.preventDefault(); save() }}>
      <input aria-label="变量名" placeholder="变量名，如 style" value={key} maxLength={48} disabled={!!editing} onChange={e => setKey(e.target.value)} />
      <select aria-label="变量类型" value={type} onChange={e => { setType(e.target.value); if (e.target.value === 'boolean') setRaw('true') }}>
        <option value="string">文本</option><option value="number">数字</option><option value="boolean">布尔</option></select>
      {type === 'boolean' ? <select aria-label="变量值" value={raw} onChange={e => setRaw(e.target.value)}><option>true</option><option>false</option></select>
        : <input aria-label="变量值" placeholder="变量值" value={raw} maxLength={2000} onChange={e => setRaw(e.target.value)} />}
      <button className="btn sm" type="submit"><Check size={13} />保存变量</button>
      <button className="btn sm ghost" type="button" onClick={() => setEditing(null)}>取消</button>
      {error && <span className="var-error" role="alert">{error}</span>}
    </form>}
  </section>
}

export function WorkflowBoard({ wf, change, disabled = false }: {
  wf: WfDef; change: (wf: WfDef) => void; disabled?: boolean
}) {
  const [selected, select] = useState('')
  const [showVars, setShowVars] = useState(false), [scale, setScale] = useState(1)
  const [preview, setPreview] = useState<{ id: string; point: Point } | null>(null)
  const drag = useRef<{ id: string; start: Point; origin: Point; next: Point; moved: boolean } | null>(null)
  const canvas = useRef<HTMLDivElement>(null)
  const points = layout(wf.steps)
  if (preview) points.set(preview.id, preview.point)
  const width = Math.max(480, ...Array.from(points.values(), p => p.x + W + 40))
  const height = Math.max(200, ...Array.from(points.values(), p => p.y + H + 24))
  const current = wf.steps.find(s => s.id === selected)
  const names = useStore(s => s.wfData?.step_catalog)
  function move(id: string, point: Point) {
    change({ ...wf, steps: wf.steps.map(s => s.id === id ? { ...s, position: point } : s) })
  }
  function inspect(id: string) {
    const header = document.getElementById('workflow-step-' + id)
    if (!header) return
    if (header.getAttribute('aria-expanded') !== 'true') header.click()
    header.scrollIntoView({ block: 'center' })
    header.focus({ preventScroll: true })
  }
  function clamp(n: number) { return Math.round(Math.max(0, Math.min(8000, n))) }
  return (
    <section className="graph-shell" aria-label="节点图">
      <header className="graph-heading"><GitBranch size={16} /><h3>节点图</h3><span className="grow" />
        <button className={'graph-vars' + (showVars ? ' active' : '')} aria-expanded={showVars} onClick={() => setShowVars(!showVars)}>
          <Braces size={14} />变量 <span>{Object.keys(wf.variables || {}).length}</span></button>
        <div className="graph-zoom"><button className="iconbtn sm" aria-label="缩小节点图" disabled={scale <= .5} onClick={() => setScale(s => s - .25)}><Minus size={14} /></button>
          <button className="graph-scale" aria-label="重置缩放" onClick={() => setScale(1)}>{Math.round(scale * 100)}%</button>
          <button className="iconbtn sm" aria-label="放大节点图" disabled={scale >= 1.5} onClick={() => setScale(s => s + .25)}><Plus size={14} /></button></div>
      </header>
      {showVars && <Variables wf={wf} change={change} disabled={disabled} />}
      <div className="graph-viewport" ref={canvas} tabIndex={0} aria-label="节点画布">
        <div style={{ width: width * scale, height: height * scale, position: 'relative' }}>
          <div className="graph-plane" style={{ width, height, transform: 'scale(' + scale + ')' }} onClick={e => { if (e.target === e.currentTarget) select('') }}>
            <svg className="graph-wires" width={width} height={height} aria-hidden="true">
              {wf.steps.flatMap(step => upstream(step).filter(id => id !== step.id && points.has(id)).map(id => {
                const source = points.get(id)!, target = points.get(step.id)!
                const x = source.x + W, y = source.y + H / 2, end = target.y + H / 2
                const bend = Math.max(28, Math.abs(target.x - x) / 2)
                return <path key={id + ':' + step.id} className={id === selected || step.id === selected ? 'selected' : ''}
                  d={`M ${x} ${y} C ${x + bend} ${y}, ${target.x - bend} ${end}, ${target.x} ${end}`} />
              }))}
            </svg>
            {wf.steps.map((step, i) => {
              const point = points.get(step.id)!, meta = NODE_TYPES[step.type], Icon = meta?.icon || FileImage
              const title = step.name.replace(/^\d+[.、]\s*/, '')
              const config = step.config
              const detail = step.type === 'llm_script' ? (config.scene_count || 3) + ' 个镜头'
                : config.width && config.height ? config.width + ' × ' + config.height : names?.find(n => n.type === step.type)?.category
              return <button type="button" key={step.id} className={'graph-node' + (step.enabled ? '' : ' off')}
                data-step-id={step.id} aria-label={'选择节点 ' + step.name} aria-pressed={step.id === selected}
                style={{ left: point.x, top: point.y, width: W, height: H }} onClick={() => select(step.id)} onDoubleClick={() => inspect(step.id)}
                onPointerDown={e => {
                  if (e.button !== 0) return
                  select(step.id)
                  if (disabled) return
                  drag.current = { id: step.id, origin: point, next: point, start: { x: e.clientX, y: e.clientY }, moved: false }
                  e.currentTarget.setPointerCapture(e.pointerId)
                }} onPointerMove={e => {
                  const d = drag.current
                  if (!d || d.id !== step.id) return
                  const dx = (e.clientX - d.start.x) / scale, dy = (e.clientY - d.start.y) / scale
                  if (!d.moved && Math.abs(dx) + Math.abs(dy) < 4) return
                  d.moved = true
                  d.next = { x: clamp(d.origin.x + dx), y: clamp(d.origin.y + dy) }
                  setPreview({ id: d.id, point: d.next })
                }} onPointerUp={() => {
                  const d = drag.current
                  if (d?.id === step.id && d.moved && !disabled) move(d.id, d.next)
                  drag.current = null; setPreview(null)
                }} onLostPointerCapture={() => { drag.current = null; setPreview(null) }}
                onKeyDown={e => {
                  if (e.key === 'Enter') { select(step.id); inspect(step.id) }
                  const offsets: Record<string, Point> = { ArrowUp: { x: 0, y: -12 }, ArrowDown: { x: 0, y: 12 }, ArrowLeft: { x: -12, y: 0 }, ArrowRight: { x: 12, y: 0 } }
                  if (e.shiftKey && !disabled && offsets[e.key]) { e.preventDefault(); move(step.id, { x: clamp(point.x + offsets[e.key].x), y: clamp(point.y + offsets[e.key].y) }) }
                }}>
                <span className="graph-node-type"><Icon size={13} />{meta?.label}<span>{i + 1}</span></span>
                <b title={title}>{title}</b><small>{detail}</small>
              </button>
            })}
          </div>
        </div>
      </div>
      <footer className="graph-footer">{current ? <><span className="graph-selection">{current.name}</span>
        <button onClick={() => inspect(current.id)}>编辑节点<ChevronRight size={13} /></button></>
        : <span>{wf.steps.length ? '选择节点可编辑参数，拖动可调整布局。' : '在下方添加步骤。'}</span>}</footer>
    </section>
  )
}
