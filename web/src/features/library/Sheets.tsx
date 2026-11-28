// 作品库相关弹层：清理、回收站、灯箱、A/B 对比、挑选参考图。
import { motion } from 'motion/react'
import { ChevronLeft, ChevronRight, Download, Film, GitCompare, ImagePlus, RotateCcw, Star, Trash2, Wind, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, media } from '../../api/client'
import type { CleanupBody, CleanupResult, Round, TrashResponse } from '../../api/types'
import { ago, cx, fmtBytes, now, rid } from '../../lib/util'
import { useStore } from '../../store/store'
import { Drawer, Modal, Scrim, Toggle, useConfirm } from '../../ui/Overlay'
import { Library } from './Library'

export function LibrarySheet() {
  const close = useStore(s => s.closeSheet)
  return <Drawer title="作品库" onClose={close}><Library inSheet /></Drawer>
}

export function CleanupSheet() {
  const close = useStore(s => s.closeSheet)
  const rounds = useStore(s => s.rounds)
  const toast = useStore(s => s.toast)
  const load = useStore(s => s.loadRounds)
  const ask = useConfirm(s => s.ask)
  const [daysOn, setDaysOn] = useState(true); const [days, setDays] = useState(30)
  const [keepOn, setKeepOn] = useState(false); const [keep, setKeep] = useState(50)
  const [mbOn, setMbOn] = useState(false); const [mb, setMb] = useState(2048)
  const [kind, setKind] = useState<'' | 'image' | 'video'>('')
  const [starred, setStarred] = useState(false); const [perm, setPerm] = useState(false)
  const [preview, setPreview] = useState<{ key: string; result?: CleanupResult; error?: string } | null>(null)
  const [revision, refresh] = useState(0)
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const body = { older_than_days: daysOn ? days : null, keep_latest: keepOn ? keep : null, max_mb: mbOn ? mb : null, kind, include_starred: starred, permanent: perm }
  const serialized = JSON.stringify(body)
  const key = revision + ':' + serialized
  const plan = preview?.key === key ? preview.result : undefined
  const err = !daysOn && !keepOn && !mbOn ? '至少勾选一个条件' : preview?.key === key ? preview.error : undefined
  useEffect(() => {
    const filters: CleanupBody = JSON.parse(serialized)
    if (filters.older_than_days == null && filters.keep_latest == null && filters.max_mb == null) return
    let active = true
    const t = setTimeout(() => api.cleanup({ ...filters, dry_run: true })
      .then(result => { if (active) setPreview({ key, result }) })
      .catch(e => { if (active) setPreview({ key, error: e instanceof Error ? e.message : '预览失败' }) }), 250)
    return () => { active = false; clearTimeout(t) }
  }, [key, serialized])
  const go = async () => {
    if (!plan?.count || inFlight.current) return
    inFlight.current = true
    setBusy(true)
    const expected_ids = [...plan.matched]
    try {
      if (body.permanent && !(await ask({ title: `永久删除 ${expected_ids.length} 个作品？`, body: '文件会立刻删除，无法恢复。', ok: '永久删除', danger: true }))) return
      const r = await api.cleanup({ ...body, expected_ids, dry_run: false })
      close(); await load()
      toast(`已清理 ${(r.deleted || []).length} 个，释放 ${fmtBytes(r.bytes)}`, 'ok', body.permanent ? undefined : { label: '撤销', fn: async () => { await api.restore(r.deleted || []); await load() } })
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) refresh(n => n + 1)
      toast(e instanceof Error ? e.message : '清理失败', 'err')
    } finally { inFlight.current = false; setBusy(false) }
  }
  return (
    <Modal title="清理旧作品" icon={<Wind size={16} />} onClose={close}
      foot={<><button className="btn" onClick={close}>取消</button><button className="btn solid-danger" disabled={busy || !plan?.count} onClick={go}><Trash2 size={14} />{plan?.count ? `删除 ${plan.count} 个` : '删除'}</button></>}>
      <label className="opt"><input type="checkbox" checked={daysOn} onChange={e => { setDaysOn(e.target.checked); setMbOn(false); refresh(n => n + 1) }} />删除 <input className="inl" type="number" min={0} value={days} onChange={e => { setDays(+e.target.value); refresh(n => n + 1) }} /> 天前生成的作品</label>
      <label className="opt"><input type="checkbox" checked={keepOn} onChange={e => { setKeepOn(e.target.checked); setMbOn(false); refresh(n => n + 1) }} />只保留最近 <input className="inl" type="number" min={0} value={keep} onChange={e => { setKeep(+e.target.value); refresh(n => n + 1) }} /> 个</label>
      <label className="opt"><input type="checkbox" checked={mbOn} onChange={e => { setMbOn(e.target.checked); if (e.target.checked) { setDaysOn(false); setKeepOn(false) } refresh(n => n + 1) }} />总占用压到 <input className="inl" type="number" min={0} value={mb} onChange={e => { setMb(+e.target.value); refresh(n => n + 1) }} /> MB 以内</label>
      <div className="row wrap">
        <select value={kind} onChange={e => { setKind(e.target.value as typeof kind); refresh(n => n + 1) }} style={{ width: 'auto' }}><option value="">图片和视频</option><option value="image">只清理图片</option><option value="video">只清理视频</option></select>
        <Toggle on={starred} onChange={v => { setStarred(v); refresh(n => n + 1) }}>包括收藏的</Toggle>
        <Toggle on={perm} onChange={v => { setPerm(v); refresh(n => n + 1) }}>跳过回收站</Toggle>
      </div>
      <div className="preview-box">
        {err ? <span className="dim">{err}</span> : !plan ? <span className="spinner" /> : plan.count ? (
          <>
            <span>将{perm ? <b className="bad-text">永久删除</b> : '移入回收站'} <b>{plan.count}</b> 个作品，释放 <b>{fmtBytes(plan.bytes)}</b>{starred ? '' : '，收藏的不动'}。</span>
            <div className="mini">{plan.matched.slice(0, 14).map(id => { const r = rounds.find(x => x.id === id); return r ? <img key={id} src={media.thumb(r)} alt={rid(id)} /> : null })}{plan.count > 14 && <span className="mini-more">+{plan.count - 14}</span>}</div>
          </>
        ) : <span className="dim">没有符合条件的作品</span>}
      </div>
      {perm && <div className="warnbox">跳过回收站的删除无法恢复。</div>}
    </Modal>
  )
}

export function TrashSheet() {
  const close = useStore(s => s.closeSheet)
  const toast = useStore(s => s.toast)
  const load = useStore(s => s.loadRounds)
  const ask = useConfirm(s => s.ask)
  const [data, setData] = useState<TrashResponse | null>(null)
  const [sel, setSel] = useState<string[]>([])
  const reload = () => api.trash().then(setData).catch(e => toast(e.message, 'err'))
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const restore = async (ids: string[]) => { const r = await api.restore(ids); toast(`已恢复 ${r.restored.length} 个`, 'ok'); setSel([]); reload(); load() }
  const purge = async (ids: string[] | 'all') => {
    const n = ids === 'all' ? data?.count : ids.length
    if (!(await ask({ title: `彻底删除 ${n} 个作品？`, body: '删除后无法恢复。', ok: '彻底删除', danger: true }))) return
    const r = await api.purge(ids === 'all' ? { all: true } : { ids })
    toast(`已彻底删除，释放 ${fmtBytes(r.bytes)}`, 'ok'); setSel([]); reload()
  }
  const items = data?.items || []
  return (
    <Modal title="回收站" icon={<Trash2 size={16} />} onClose={close} wide
      foot={<>
        <span className="dim grow">{data ? `${data.count} 个 · ${fmtBytes(data.bytes)} · 保留 ${data.retention_days} 天` : ''}</span>
        <button className="btn" disabled={!sel.length} onClick={() => restore(sel)}><RotateCcw size={14} />恢复所选</button>
        <button className="btn danger" disabled={!sel.length} onClick={() => purge(sel)}>彻底删除所选</button>
        <button className="btn solid-danger" disabled={!items.length} onClick={() => purge('all')}>清空回收站</button>
      </>}>
      {!items.length ? <div className="empty"><Trash2 size={20} /><b>回收站是空的</b><span>删除的作品会在这里保留 7 天。</span></div> : (
        <>
          <div className="row"><button className="btn sm ghost" onClick={() => setSel(sel.length === items.length ? [] : items.map(i => i.id))}>{sel.length === items.length ? '取消全选' : '全选'}</button></div>
          <div className="trash-grid">
            {items.map(r => (
              <button key={r.id} className={cx('trash-tile', sel.includes(r.id) && 'sel')} onClick={() => setSel(s => s.includes(r.id) ? s.filter(x => x !== r.id) : [...s, r.id])}>
                <img src={media.trashThumb(r)} alt="" />
                <span className="tile-id">{rid(r.id)}</span>
                <span className="trash-meta">{r.purge_at ? `${Math.max(0, Math.ceil((r.purge_at - now()) / 86400))} 天后清除` : ''}</span>
                <span className={cx('tile-check', sel.includes(r.id) && 'on')} />
              </button>
            ))}
          </div>
        </>
      )}
    </Modal>
  )
}

export function Lightbox() {
  const args = useStore(s => s.sheetArgs)
  const close = useStore(s => s.closeSheet)
  const rounds = useStore(s => s.rounds)
  const setViewing = useStore(s => s.setViewing)
  const [id, setId] = useState(String(args.id || ''))
  const r = rounds.find(x => x.id === id)
  const i = rounds.findIndex(x => x.id === id)
  const go = (d: number) => { if (!rounds.length) return; const n = rounds[(i + d + rounds.length) % rounds.length]; setId(n.id); setViewing(n.id) }
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'ArrowLeft') go(-1); if (e.key === 'ArrowRight') go(1) }
    document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k)
  })
  if (!r) return null
  return (
    <Scrim onClose={close}>
      <div className="lightbox">
        <motion.div key={r.id} className="lb-media" initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }}>
          {r.kind === 'video' && !__MOCK__ ? <video src={media.round(r.id)} controls autoPlay loop /> : <img src={media.round(r.id, r.mtime)} alt="" />}
        </motion.div>
        <div className="lb-bar glass">
          <b>{rid(r.id)}</b><span className="dim">{r.width}×{r.height} · {ago(r.created_at)}</span>
          <span className="grow" />
          <a className="iconbtn" href={media.download(r.id)} download aria-label="下载"><Download size={16} /></a>
          <button className="iconbtn" onClick={close} aria-label="关闭"><X size={16} /></button>
        </div>
        <button className="vnav l" onClick={() => go(-1)} aria-label="上一张"><ChevronLeft size={22} /></button>
        <button className="vnav r" onClick={() => go(1)} aria-label="下一张"><ChevronRight size={22} /></button>
      </div>
    </Scrim>
  )
}

export function CompareSheet() {
  const args = useStore(s => s.sheetArgs)
  const close = useStore(s => s.closeSheet)
  const rounds = useStore(s => s.rounds)
  const imgs = rounds.filter(r => r.kind === 'image')
  const [a, setA] = useState(String(args.a || args.id || imgs[0]?.id || ''))
  const [b, setB] = useState(String(args.b || imgs.find(r => r.id !== (args.a || args.id))?.id || ''))
  const [pos, setPos] = useState(50)
  const box = useRef<HTMLDivElement>(null)
  const ra = imgs.find(r => r.id === a), rb = imgs.find(r => r.id === b)
  const move = (x: number) => { const el = box.current; if (!el) return; const rc = el.getBoundingClientRect(); setPos(Math.max(0, Math.min(100, (x - rc.left) / rc.width * 100))) }
  return (
    <Modal title="A / B 对比" icon={<GitCompare size={16} />} onClose={close} wide>
      <div className="g2">
        <select value={a} onChange={e => setA(e.target.value)}>{imgs.map(r => <option key={r.id} value={r.id}>A · {rid(r.id)} {r.prompt.slice(0, 24)}</option>)}</select>
        <select value={b} onChange={e => setB(e.target.value)}>{imgs.map(r => <option key={r.id} value={r.id}>B · {rid(r.id)} {r.prompt.slice(0, 24)}</option>)}</select>
      </div>
      {ra && rb ? (
        <div ref={box} className="compare" style={{ aspectRatio: `${ra.width || 1}/${ra.height || 1}` }}
          onPointerDown={e => { (e.target as HTMLElement).setPointerCapture(e.pointerId); move(e.clientX) }}
          onPointerMove={e => { if (e.buttons) move(e.clientX) }}>
          <img src={media.round(rb.id, rb.mtime)} alt="B" />
          <img src={media.round(ra.id, ra.mtime)} alt="A" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} />
          <span className="cmp-line" style={{ left: `${pos}%` }}><i /></span>
          <span className="cmp-tag l">A</span><span className="cmp-tag r">B</span>
        </div>
      ) : <div className="empty"><b>至少需要两张图片</b></div>}
      <p className="help">拖动画面里的分隔线查看细节差异。</p>
    </Modal>
  )
}

export function PickerSheet() {
  const args = useStore(s => s.sheetArgs)
  const close = useStore(s => s.closeSheet)
  const rounds = useStore(s => s.rounds)
  const toast = useStore(s => s.toast)
  const patch = useStore(s => s.patchDraft)
  const onPick = args.onPick as ((r: Round) => void) | undefined
  const videos = args.slot === 'video'
  const character = args.slot === 'first' && args.character === true
  const items = useMemo(() => rounds.filter(r => r.kind === (videos ? 'video' : 'image')), [rounds, videos])
  const setVideoRef = useStore(s => s.setVideoRef)
  const videoRefBusy = useStore(s => s.videoRefBusy)
  const pick = async (r: Round) => {
    if (onPick) { close(); onPick(r); return }
    if (videos) { if (await setVideoRef(r.id)) close(); return }
    try {
      const slot = (args.slot as 'first' | 'last') || 'first'
      const st0 = useStore.getState().status
      const keyframe = slot === 'first' && args.keyframe === true
      const res = await api.useRound(r.id, slot, slot === 'first' && !keyframe && !character && !!st0?.references.items.length)
      const st = useStore.getState().status; if (st) useStore.setState({ status: { ...st, references: res.references } })
      if (slot === 'first' && useStore.getState().workspace === 'image') patch({ useRef: true, chain: false })
      if (keyframe) patch({ useFirstFrame: true })
      toast(`已将 ${rid(r.id)} 设为${slot === 'last' ? '尾帧' : keyframe ? '首帧' : character ? '人设图' : '参考图'}`, 'ok'); close()
    } catch (e) { toast(e instanceof Error ? e.message : '设置失败', 'err') }
  }
  return (
    <Modal title={videos ? '从作品库选视频' : character ? '从作品库选人设图' : '从作品库挑选'} icon={videos ? <Film size={16} /> : <ImagePlus size={16} />} onClose={close} wide>
      {!items.length ? <div className="empty"><b>{videos ? '作品库里还没有视频' : '作品库里还没有图片'}</b></div> : (
        <div className="trash-grid">
          {items.map(r => (
            <button key={r.id} className="trash-tile" disabled={videos && videoRefBusy} onClick={() => pick(r)} title={r.prompt}>
              {videos && !r.has_thumb ? <Film size={24} /> : <img src={media.thumb(r)} alt="" />}<span className="tile-id">{rid(r.id)}</span>
              {r.starred && <span className="tile-star"><Star size={11} fill="currentColor" /></span>}
            </button>
          ))}
        </div>
      )}
    </Modal>
  )
}
export const _icons = { Film }
