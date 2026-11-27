// 舞台：当前作品、生成进度、任务队列。作品浮在玻璃面上，是整个界面的视觉中心。
import { AnimatePresence, motion } from 'motion/react'
import { ChevronLeft, ChevronRight, Copy, Download, Expand, Film, GitCompare, ImageIcon, RefreshCw, Star, Trash2, X } from 'lucide-react'
import { api, media } from '../../api/client'
import type { Job, Round } from '../../api/types'
import { ago, clock, cx, now, rid } from '../../lib/util'
import { comfyDraftFields, useStore } from '../../store/store'
import { useConfirm, useTick } from '../../ui/Overlay'

const STAGES: [Job['stage'], string][] = [['provisioning', '申请实例'], ['uploading', '上传参数'], ['generating', '采样'], ['downloading', '回传']]
const EMPTY_QUEUE: Job[] = []

export function Stage() {
  const status = useStore(s => s.status)
  const rounds = useStore(s => s.rounds)
  const viewing = useStore(s => s.viewing)
  const setViewing = useStore(s => s.setViewing)
  const filter = useStore(s => s.galleryFilter)
  const job = status?.current
  useTick(1000)

  const visible = rounds.filter(r => (!filter.kind || r.kind === filter.kind) && (!filter.starred || r.starred) && (!filter.q || `${r.prompt} ${r.id} ${r.model}`.toLowerCase().includes(filter.q.toLowerCase())))
  const current = viewing ? rounds.find(r => r.id === viewing) || null : null
  const idx = current ? visible.findIndex(r => r.id === current.id) : -1
  const step = (d: number) => { if (!visible.length) return; const i = idx < 0 ? 0 : (idx + d + visible.length) % visible.length; setViewing(visible[i].id) }

  return (
    <section className="stage">
      <div className="stage-frame glass">
        <AnimatePresence mode="wait">
          {job && !current ? <Progress key="progress" job={job} /> : current ? <Viewer key={current.id} round={current} onStep={step} hasNav={visible.length > 1} /> : <EmptyStage key="empty" hasHistory={rounds.length > 0} />}
        </AnimatePresence>
      </div>
      {job && current && <div className="stage-progress"><Progress job={job} compact /></div>}
      <Queue />
      {current && <ActionBar round={current} />}
    </section>
  )
}

function EmptyStage({ hasHistory }: { hasHistory: boolean }) {
  const setLibOpen = useStore(s => s.setLibraryOpen)
  return (
    <motion.div className="stage-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <span className="stage-mark"><Film size={26} /></span>
      <h3>{hasHistory ? '选一张作品，或直接生成新的' : '从左边开始'}</h3>
      <p>{hasHistory ? '作品库里已有作品，点开缩略图即可在这里查看。' : '写一句想法，选好模型，点「开始生成」。成品会留在作品库里。'}</p>
      {hasHistory && <button className="btn sm" onClick={() => setLibOpen(true)}>打开作品库</button>}
    </motion.div>
  )
}

function Viewer({ round, onStep, hasNav }: { round: Round; onStep: (d: number) => void; hasNav: boolean }) {
  const open = useStore(s => s.openSheet)
  const src = media.round(round.id, round.mtime)
  return (
    <motion.div className="viewer" initial={{ opacity: 0, scale: 0.985 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
      {round.kind === 'video' && !__MOCK__
        ? <video src={src} controls autoPlay loop playsInline poster={round.has_thumb ? media.thumb(round) : undefined} />
        : <img src={src} alt={round.prompt.slice(0, 80)} />}
      {hasNav && <>
        <button className="vnav l" onClick={() => onStep(-1)} aria-label="上一张"><ChevronLeft size={20} /></button>
        <button className="vnav r" onClick={() => onStep(1)} aria-label="下一张"><ChevronRight size={20} /></button>
      </>}
      <button className="vnav expand" onClick={() => open('lightbox', { id: round.id })} aria-label="全屏查看"><Expand size={15} /></button>
    </motion.div>
  )
}

function Progress({ job, compact }: { job: Job; compact?: boolean }) {
  const toast = useStore(s => s.toast)
  const pr = job.progress
  const pct = pr?.pct
  const idx = STAGES.findIndex(s => s[0] === job.stage)
  const cancel = async () => { try { await api.stop(false); toast('已取消', 'ok') } catch (e) { toast(e instanceof Error ? e.message : '取消失败', 'err') } }
  const elapsed = job.started_at ? clock(now() - job.started_at) : ''
  return (
    <motion.div className={cx('progress', compact && 'compact')} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {!compact && <div className="progress-art"><span className="spinner lg" /></div>}
      <div className="progress-body">
        <div className="row between">
          <b>{(STAGES.find(s => s[0] === job.stage)?.[1]) || job.stage}{pr?.label ? ` · ${pr.label}` : ''}{pr?.detail ? ` ${pr.detail}` : ''}</b>
          <span className="dim">{job.mode === 'video' ? `MiniMax-H3 ${job.workflow || ''}` : job.model} · {job.width}×{job.height} · seed {job.seed}</span>
          <span className="grow" />
          <span className="dim tabular">{elapsed && `已用 ${elapsed}`}{pr?.rate ? ` · ${pr.rate}` : ''}</span>
          <button className="btn sm danger" onClick={cancel}><X size={13} />取消</button>
        </div>
        <div className={cx('bar', pct == null && 'indet')}><i style={{ width: pct == null ? undefined : `${pct}%` }} /></div>
        <div className="steps-line">{STAGES.map((s, i) => <span key={s[0]} className={cx(i < idx && 'done', i === idx && 'cur')}>{s[1]}</span>)}</div>
      </div>
    </motion.div>
  )
}

function Queue() {
  const q = useStore(s => s.status?.queue) || EMPTY_QUEUE
  const toast = useStore(s => s.toast)
  if (!q.length) return null
  return (
    <div className="queue glass">
      <div className="row between"><b>排队中</b><span className="dim">{q.length} 个</span><span className="grow" /><button className="btn sm ghost" onClick={async () => { await api.clearQueue(); toast('队列已清空', 'ok') }}>清空队列</button></div>
      {q.map((j, i) => (
        <div className="qrow" key={j.id}>
          <span className="n">{i + 1}</span>{j.mode === 'video' ? <Film size={13} /> : <ImageIcon size={13} />}
          <span className="q-prompt">{j.prompt}</span><span className="dim">{j.width}×{j.height} · seed {j.seed}</span>
          <button className="iconbtn sm" title="移出队列" onClick={async () => { try { await api.unqueue(j.id) } catch (e) { toast(e instanceof Error ? e.message : '移除失败', 'err') } }}><X size={13} /></button>
        </div>
      ))}
    </div>
  )
}

function ActionBar({ round }: { round: Round }) {
  const toast = useStore(s => s.toast)
  const open = useStore(s => s.openSheet)
  const patch = useStore(s => s.patchDraft)
  const setWs = useStore(s => s.setWorkspace)
  const setViewing = useStore(s => s.setViewing)
  const ask = useConfirm(s => s.ask)
  const loadRounds = useStore(s => s.loadRounds)

  const star = async () => {
    try { await api.star([round.id], !round.starred); await loadRounds(); toast(round.starred ? '已取消收藏' : '已收藏', 'ok') }
    catch (e) { toast(e instanceof Error ? e.message : '操作失败', 'err') }
  }
  const del = async () => {
    const ok = await ask({ title: `删除作品 ${rid(round.id)}？`, body: '会移入回收站，7 天内可以恢复。', ok: '删除', danger: true })
    if (!ok) return
    try {
      const r = await api.deleteRounds([round.id])
      setViewing(null); await loadRounds()
      toast('已删除', 'ok', { label: '撤销', fn: async () => { await api.restore(r.deleted); await loadRounds() } })
    } catch (e) { toast(e instanceof Error ? e.message : '删除失败', 'err') }
  }
  const reuse = () => {
    const m = round
    const comfy = m.kind === 'image' && m.engine === 'comfyui' ? comfyDraftFields(m.comfy) : null
    if (m.kind === 'video') setWs('video'); else setWs('image')
    patch({
      prompt: m.prompt, negative: m.negative || '', width: m.width || 768, height: m.height || 1152,
      steps: m.steps || 35, cfg: m.cfg || 5, seed: m.seed != null ? String(m.seed) : '-1', gpu: m.gpu || 'A100',
      ...(m.kind === 'video'
        ? { workflow: (m.workflow as 't2va') || 't2va', frames: m.num_frames || 124, offload: m.offload_mode || 'auto' }
        : comfy ? { engine: 'comfyui', ...comfy } : { engine: 'diffusers', model: m.model }),
      loras: m.loras || [],
    })
    if (comfy && (!comfy.comfyDiff || !comfy.comfyTe || !comfy.comfyVae)) {
      toast('已填回可用参数，请补齐历史记录中缺少的模型链接', 'err')
    } else toast(`已填回 ${rid(round.id)} 的参数`, 'ok')
  }
  const asRef = async (slot: 'first' | 'last') => {
    try {
      const r = await api.useRound(round.id, slot)
      const st = useStore.getState().status; if (st) useStore.setState({ status: { ...st, references: r.references } })
      if (slot === 'first') patch({ useRef: true, chain: false })
      toast(slot === 'last' ? '已设为尾帧' : '已设为参考图', 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '设置失败', 'err') }
  }
  const toVideo = async () => { await asRef('first'); setWs('video'); patch({ workflow: 'fl2va' }) }
  const copy = async () => { try { await navigator.clipboard.writeText(round.prompt); toast('提示词已复制', 'ok') } catch { toast('复制失败', 'err') } }

  return (
    <div className="actionbar glass">
      <div className="ab-title">
        <b>{rid(round.id)}</b>
        <span className="dim">{round.kind === 'video' ? '视频' : '图片'} · {round.width}×{round.height} · {round.model} · {ago(round.created_at)}</span>
      </div>
      <div className="ab-actions">
        <button className={cx('btn sm', round.starred && 'starred')} onClick={star} title="收藏 (S)"><Star size={14} />{round.starred ? '已收藏' : '收藏'}</button>
        {round.kind === 'image' && <button className="btn sm" onClick={() => asRef('first')}><ImageIcon size={14} />设为参考</button>}
        {round.kind === 'image' && <button className="btn sm" onClick={() => asRef('last')}><Film size={14} />设为尾帧</button>}
        {round.kind === 'image' && <button className="btn sm" onClick={toVideo}><ClapperIcon />做成视频</button>}
        {round.kind === 'image' && <button className="btn sm" onClick={() => open('compare', { id: round.id })}><GitCompare size={14} />对比</button>}
        <button className="btn sm" onClick={reuse}><RefreshCw size={14} />复用参数</button>
        <a className="btn sm" href={media.download(round.id)} download><Download size={14} />下载</a>
        <button className="btn sm danger" onClick={del}><Trash2 size={14} />删除</button>
        <button className="btn sm ghost" onClick={() => setViewing(null)} title="收起"><X size={14} /></button>
      </div>
      <div className="ab-prompt"><button className="iconbtn sm" onClick={copy} title="复制提示词"><Copy size={13} /></button><span>{round.prompt}</span></div>
      <div className="ab-tags">
        {round.seed != null && <span className="tag">seed {round.seed}</span>}
        {round.steps != null && <span className="tag">{round.steps} 步</span>}
        {round.cfg != null && <span className="tag">CFG {round.cfg}</span>}
        {round.gpu && <span className="tag">{round.gpu}</span>}
        {round.workflow && <span className="tag">{round.workflow}</span>}
        {round.num_frames != null && <span className="tag">{round.num_frames} 帧</span>}
        {round.duration_s != null && <span className="tag">{round.duration_s}s</span>}
        {(round.loras || []).map((l, i) => <span className="tag" key={i}>{l.repo_id.split('/').pop()} ×{l.scale}</span>)}
      </div>
    </div>
  )
}
function ClapperIcon() { return <Film size={14} /> }
