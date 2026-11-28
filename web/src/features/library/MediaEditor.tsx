import { Brush, Crop, ImageIcon, Scissors, Undo2 } from 'lucide-react'
import { useRef, useState, type PointerEvent } from 'react'
import { api, media } from '../../api/client'
import type { BrushStroke, CropBox, Round } from '../../api/types'
import { clamp, rid } from '../../lib/util'
import { useStore } from '../../store/store'
import { Modal, Seg } from '../../ui/Overlay'

export function MediaEditor({ mode }: { mode: 'mask' | 'crop' | 'clip' }) {
  const id = useStore(s => s.sheetArgs.id)
  const round = useStore(s => s.rounds.find(r => r.id === id))
  const close = useStore(s => s.closeSheet)
  if (!round) return <Modal title="素材已移除" onClose={close}><p>请从作品库重新选择。</p></Modal>
  if (mode === 'crop') return <CropEditor key={round.id} round={round} />
  return mode === 'mask' ? <MaskEditor key={round.id} round={round} /> : <ClipEditor key={round.id} round={round} />
}

function CropEditor({ round }: { round: Round }) {
  const close = useStore(s => s.closeSheet)
  const [size, setSize] = useState<{ width: number; height: number } | null>(null)
  const [selection, setSelection] = useState<CropBox | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  const drag = useRef<{ id: number; x: number; y: number; move: CropBox | null } | null>(null)
  const w = size?.width || round.width || 1, h = size?.height || round.height || 1
  const box = selection ?? { x: 0, y: 0, width: w, height: h }
  const position = (e: PointerEvent<HTMLDivElement>) => {
    const bounds = e.currentTarget.getBoundingClientRect()
    return { x: clamp(Math.round((e.clientX - bounds.left) * w / bounds.width), 0, w),
      y: clamp(Math.round((e.clientY - bounds.top) * h / bounds.height), 0, h) }
  }
  const move = (e: PointerEvent<HTMLDivElement>) => {
    const start = drag.current
    if (!start || start.id !== e.pointerId) return
    const { x, y } = position(e)
    if (start.move) {
      const b = start.move
      setSelection({ ...b, x: clamp(b.x + x - start.x, 0, w - b.width), y: clamp(b.y + y - start.y, 0, h - b.height) })
    } else if (x !== start.x && y !== start.y) {
      setSelection({ x: Math.min(x, start.x), y: Math.min(y, start.y), width: Math.abs(x - start.x), height: Math.abs(y - start.y) })
    }
  }
  const preset = (ratio: number) => {
    const width = Math.max(1, Math.min(w, Math.round(h * ratio))), height = Math.max(1, Math.min(h, Math.round(w / ratio)))
    setSelection({ x: Math.floor((w - width) / 2), y: Math.floor((h - height) / 2), width, height })
  }
  const change = (key: keyof CropBox, value: number) => {
    if (!Number.isFinite(value)) return
    const b = { ...box, [key]: Math.round(value) }
    b.x = clamp(b.x, 0, w - 1); b.y = clamp(b.y, 0, h - 1)
    b.width = clamp(b.width, 1, w - b.x); b.height = clamp(b.height, 1, h - b.y)
    setSelection(b)
  }
  const save = async () => {
    if (!size || !selection || pending.current) return
    pending.current = true
    setBusy(true); setError('')
    try {
      const { id } = await api.crop(round.id, selection)
      await useStore.getState().loadRounds()
      const s = useStore.getState()
      if (s.sheet === 'crop' && s.sheetArgs.id === round.id) { s.setViewing(id); close() }
      s.toast(`裁好的图片已存为作品 ${rid(id)}`, 'ok')
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败') }
    finally { pending.current = false; setBusy(false) }
  }
  return <Modal wide title={`裁图 · ${rid(round.id)}`} icon={<Crop size={16} />} onClose={close}
    foot={<><button className="btn" onClick={close}>取消</button><button className="btn primary" disabled={!size || busy || (box.width === w && box.height === h)} onClick={save}>{busy ? '正在保存…' : '保存裁图'}</button></>}>
    <div className="edit-surface"><div className="crop-canvas" style={{ width: `min(100%, ${46 * w / h}dvh)` }}
      onPointerDown={e => {
        if (!size || busy || e.button !== 0 || drag.current) return
        drag.current = { id: e.pointerId, ...position(e), move: e.target instanceof HTMLElement && e.target.classList.contains('crop-selection') ? selection : null }
        e.currentTarget.setPointerCapture(e.pointerId)
      }} onPointerMove={move} onPointerUp={move} onLostPointerCapture={() => { drag.current = null }}>
      <img src={media.round(round.id, round.mtime)} alt="裁剪原图" draggable={false}
        onLoad={e => setSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })}
        onError={() => { setSize(null); setError('无法加载原图，请重新打开作品。') }} />
      {selection && <div className="crop-selection" style={{ left: `${100 * box.x / w}%`, top: `${100 * box.y / h}%`,
        width: `${100 * box.width / w}%`, height: `${100 * box.height / h}%` }} />}
    </div></div>
    <div className="edit-toolbar crop-controls">
      <div className="chips" role="group" aria-label="裁剪比例">
        {([[1, '1:1'], [16 / 9, '16:9'], [9 / 16, '9:16']] as const).map(([ratio, label]) =>
          <button key={label} className="chip" disabled={!size || busy} onClick={() => preset(ratio)}>{label}</button>)}
        <button className="mini-link" disabled={!selection || busy} onClick={() => setSelection(null)}>重选</button>
      </div>
      <output aria-label="选区尺寸">{box.width} × {box.height} px</output>
    </div>
    <p className="help">在图上拖出选区，拖动选区可调整位置。</p>
    <details className="fold"><summary>像素坐标</summary><div className="crop-fields">
      {([['x', '左边距', w - 1], ['y', '上边距', h - 1], ['width', '宽度', w - box.x], ['height', '高度', h - box.y]] as const).map(([key, label, max]) =>
        <label className="field" key={key}><span className="fl">{label}</span><input type="number" disabled={!size || busy}
          min={key === 'x' || key === 'y' ? 0 : 1} max={max} value={box[key]} onChange={e => change(key, e.target.valueAsNumber)} /></label>)}
    </div></details>
    {error && <p role="alert" className="bad-text">{error}</p>}
  </Modal>
}

function MaskEditor({ round }: { round: Round }) {
  const existing = useStore(s => s.draft.editMask)
  const close = useStore(s => s.closeSheet)
  const toast = useStore(s => s.toast)
  const [strokes, setStrokes] = useState<BrushStroke[]>(existing?.source_id === round.id ? existing.strokes : [])
  const [size, setSize] = useState(8)
  const [loaded, setLoaded] = useState(false)
  const pointer = useRef<number | null>(null)
  const count = useRef(strokes.reduce((n, s) => n + s.points.length, 0))
  const w = round.width || 1, h = round.height || 1
  const point = (e: PointerEvent<SVGSVGElement>): [number, number] => {
    const bounds = e.currentTarget.getBoundingClientRect()
    return [clamp((e.clientX - bounds.left) / bounds.width, 0, 1), clamp((e.clientY - bounds.top) / bounds.height, 0, 1)]
  }
  const start = (e: PointerEvent<SVGSVGElement>) => {
    if (!loaded || e.button !== 0 || pointer.current !== null) return
    if (strokes.length >= 256 || count.current >= 12000) { toast('笔迹已满，请撤销部分笔迹', 'err'); return }
    e.currentTarget.setPointerCapture(e.pointerId)
    pointer.current = e.pointerId
    const first = point(e)
    count.current++
    setStrokes(old => [...old, { size: size / 100, points: [first] }])
  }
  const move = (e: PointerEvent<SVGSVGElement>) => {
    if (pointer.current !== e.pointerId || count.current >= 12000) return
    const next = point(e)
    count.current++
    setStrokes(old => {
      const last = old[old.length - 1]
      return [...old.slice(0, -1), { ...last, points: [...last.points, next] }]
    })
  }
  const apply = () => {
    const s = useStore.getState()
    s.setWorkspace('image')
    s.patchDraft({ editMask: { source_id: round.id, strokes }, useRef: false, chain: false })
    close()
    toast('选区已保存，请填写修改要求', 'ok')
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('.composer textarea[rows="4"]')?.focus())
  }

  return <Modal wide title={`局部改图 · ${rid(round.id)}`} icon={<Brush size={16} />} onClose={close}
    foot={<><button className="btn" onClick={close}>取消</button><button className="btn primary" disabled={!loaded || !strokes.length} onClick={apply}>使用这个选区</button></>}>
    <div className="edit-surface">
      <svg className="mask-canvas" style={{ width: `min(100%, ${46 * w / h}dvh)` }} viewBox={`0 0 ${w} ${h}`} aria-label="在原图上涂抹修改区域"
        onPointerDown={start} onPointerMove={move} onLostPointerCapture={() => { pointer.current = null }}>
        <image href={media.round(round.id, round.mtime)} width={w} height={h} onLoad={() => setLoaded(true)}
          onError={() => { setLoaded(false); toast('原图读取失败，请重新打开', 'err') }} />
        <g opacity={0.56} fill="currentColor" stroke="currentColor">
          {strokes.map((s, i) => {
            const d = s.size * Math.min(w, h)
            return s.points.length === 1
              ? <circle key={i} cx={s.points[0][0] * w} cy={s.points[0][1] * h} r={d / 2} stroke="none" />
              : <polyline key={i} points={s.points.map(([x, y]) => `${x * w},${y * h}`).join(' ')} fill="none" strokeWidth={d} strokeLinecap="round" strokeLinejoin="round" />
          })}
        </g>
      </svg>
    </div>
    <div className="edit-toolbar">
      <label className="brush-width">笔刷 <input type="range" min="1" max="40" value={size} onChange={e => setSize(+e.target.value)} /> <output>{size}%</output></label>
      <button className="btn sm" disabled={!strokes.length} onClick={() => {
        count.current -= strokes[strokes.length - 1].points.length
        setStrokes(strokes.slice(0, -1))
      }}><Undo2 size={14} />撤销一笔</button>
    </div>
    <p className="help">涂出要修改的位置，成图沿用原图尺寸。</p>
  </Modal>
}

function ClipEditor({ round }: { round: Round }) {
  const close = useStore(s => s.closeSheet)
  const toast = useStore(s => s.toast)
  const video = useRef<HTMLVideoElement>(null)
  const [duration, setDuration] = useState(round.media_duration_s || 0)
  const [current, setCurrent] = useState(0)
  const [ready, setReady] = useState(false)
  const [tab, setTab] = useState<'frame' | 'clip'>('frame')
  const [start, setStart] = useState('0')
  const [end, setEnd] = useState(duration ? String(duration) : '')
  const [mute, setMute] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  const valid = start.trim() !== '' && end.trim() !== '' && +start >= 0 && +end > +start && +end <= duration + 0.001
  const at = () => Math.min(video.current?.currentTime ?? 0, duration)
  const save = async (position?: 'first' | 'time' | 'last') => {
    if (pending.current) return
    pending.current = true
    video.current?.pause()
    setBusy(true); setError('')
    try {
      const result = position ? await api.frame(round.id, position, position === 'time' ? at() : 0) : await api.clip(round.id, +start, +end, mute)
      await useStore.getState().loadRounds()
      const s = useStore.getState()
      if (s.sheet === 'clip' && s.sheetArgs.id === round.id) {
        s.setViewing(result.id); close()
      }
      toast(`${position ? '画面' : '片段'}已存为作品 ${rid(result.id)}`, 'ok')
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败') }
    finally { pending.current = false; setBusy(false) }
  }
  return <Modal wide title={`取帧与裁段 · ${rid(round.id)}`} icon={<Scissors size={16} />} onClose={close}>
    {__MOCK__ ? <p className="help">取帧与裁段需要连接工作台的 FFmpeg 服务。</p> : <>
      <video ref={video} className="clip-preview" src={media.round(round.id)} poster={round.has_thumb ? media.thumb(round) : undefined}
        aria-label="源视频预览" controls preload="auto" playsInline onLoadedMetadata={e => {
          const seconds = round.media_duration_s || e.currentTarget.duration
          if (Number.isFinite(seconds) && seconds > 0) { setDuration(seconds); setEnd(String(seconds)) }
        }} onLoadedData={() => setReady(true)} onTimeUpdate={() => setCurrent(at())} onError={() => { setReady(false); setError('浏览器无法预览此视频，仍可按时间裁段或提取首尾帧。') }} />
      <Seg ariaLabel="视频工具" value={tab} onChange={setTab} options={[{ id: 'frame', label: '取帧', icon: <ImageIcon size={14} /> }, { id: 'clip', label: '裁段', icon: <Scissors size={14} /> }]} />
      {tab === 'frame' ? <div className="edit-toolbar">
        <button className="btn sm" disabled={busy} onClick={() => save('first')}>提取首帧</button>
        <button className="btn sm primary" disabled={busy || !ready} onClick={() => save('time')}>提取当前帧 · {current.toFixed(2)} 秒</button>
        <button className="btn sm" disabled={busy} onClick={() => save('last')}>提取尾帧</button>
      </div> : <>
        <div className="clip-times">
          {([['开始', start, setStart], ['结束', end, setEnd]] as const).map(([label, value, set]) => <div key={label}>
            <label className="field"><span className="fl">{label}（秒）</span><input type="number" min="0" max={duration} step="any" value={value} onChange={e => set(e.target.value)} /></label>
            <button className="mini-link" disabled={!ready} onClick={() => set(String(+at().toFixed(4)))}>用当前时间</button>
          </div>)}
        </div>
        <div className="edit-toolbar">
          <label className="opt"><input type="checkbox" checked={mute} onChange={e => setMute(e.target.checked)} />移除音轨</label>
          <button className="btn primary" disabled={busy || !valid} onClick={() => save()}>保存片段{valid ? ` · ${+(+end - +start).toFixed(2)} 秒` : ''}</button>
        </div>
        {!valid && <p className="help">请选择 0 到 {duration.toFixed(2)} 秒之间的起止时间。</p>}
      </>}
      {busy && <p role="status" className="help">正在保存到作品库…</p>}
      {error && <p role="alert" className="bad-text">{error}</p>}
    </>}
  </Modal>
}
