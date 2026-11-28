// 作品库：宽屏时常驻右侧，窄屏时作为抽屉打开。按日期分组，支持筛选、搜索、多选和拖拽到参考图。
import { motion } from 'motion/react'
import { CheckSquare, Film, Search, Sparkles, Star, Trash2, Upload, Wind, X } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { api, media } from '../../api/client'
import type { Round } from '../../api/types'
import { cx, dateLabel, fmtBytes, rid } from '../../lib/util'
import { useStore } from '../../store/store'
import { useConfirm } from '../../ui/Overlay'

const PAGE = 60

export function Library({ inSheet }: { inSheet?: boolean }) {
  const rounds = useStore(s => s.rounds)
  const filter = useStore(s => s.galleryFilter)
  const viewing = useStore(s => s.viewing)
  const setViewing = useStore(s => s.setViewing)
  const selecting = useStore(s => s.selecting)
  const selected = useStore(s => s.selected)
  const toggle = useStore(s => s.toggleSelect)
  const open = useStore(s => s.openSheet)
  const close = useStore(s => s.closeSheet)
  const [page, setPage] = useState(PAGE)
  const input = useRef<HTMLInputElement>(null)
  const [importing, setImporting] = useState(false)
  const showRound = (id: string) => {
    setViewing(id)
    if (inSheet) close()
    else if (matchMedia('(max-width: 1180px)').matches) useStore.getState().setLibraryOpen(false)
    if (matchMedia('(max-width: 760px)').matches) requestAnimationFrame(() => document.querySelector('.stage')?.scrollIntoView())
  }
  const importFile = async (file: File) => {
    const s = useStore.getState()
    const kind = file.type === 'video/mp4' || /\.mp4$/i.test(file.name) ? 'video' : 'image'
    const max = kind === 'video' ? s.cfg?.limits.video_upload_max_mb || 64 : s.cfg?.limits.upload_max_mb || 12
    if (file.size > max * 1048576) { s.toast(`文件超过 ${max} MB`, 'err'); return }
    setImporting(true)
    try {
      const r = await api.importMedia(file, kind)
      await s.loadRounds()
      useStore.setState({ galleryFilter: { kind: '', q: '', starred: false } })
      showRound(r.id)
      s.toast(`已导入 ${rid(r.id)}`, 'ok')
    } catch (e) { s.toast(e instanceof Error ? e.message : '导入失败', 'err') }
    finally { setImporting(false) }
  }

  const setFilter = (p: Partial<typeof filter>) => { useStore.setState({ galleryFilter: { ...filter, ...p } }); setPage(PAGE) }
  const items = useMemo(() => {
    const q = filter.q.trim().toLowerCase()
    const qn = /^\d+$/.test(q) ? String(+q) : null
    return rounds.filter(r =>
      (!filter.kind || r.kind === filter.kind) && (!filter.starred || r.starred) &&
      (!q || r.prompt.toLowerCase().includes(q) || r.model.toLowerCase().includes(q) || (qn != null && String(+r.id) === qn)))
  }, [rounds, filter])
  const groups = useMemo(() => {
    const g: { label: string; items: Round[] }[] = []
    for (const r of items.slice(0, page)) {
      const l = dateLabel(r.created_at)
      if (g.length && g[g.length - 1].label === l) g[g.length - 1].items.push(r)
      else g.push({ label: l, items: [r] })
    }
    return g
  }, [items, page])
  const stats = { all: rounds.length, image: rounds.filter(r => r.kind === 'image').length, video: rounds.filter(r => r.kind === 'video').length, star: rounds.filter(r => r.starred).length }
  const bytes = rounds.reduce((a, r) => a + r.bytes, 0)

  const onTile = (r: Round, e: React.MouseEvent) => {
    if (selecting || e.metaKey || e.ctrlKey) { if (!selecting) useStore.setState({ selecting: true }); toggle(r.id); return }
    showRound(r.id)
  }

  return (
    <div className={cx('library', inSheet && 'in-sheet')}>
      <div className="lib-head">
        <h2>作品库</h2><span className="dim tabular">{stats.all} 个 · {fmtBytes(bytes)}</span>
        <span className="grow" />
        <button className={cx('iconbtn sm', selecting && 'on')} title="多选" onClick={() => useStore.setState({ selecting: !selecting, selected: [] })}><CheckSquare size={15} /></button>
        <button className="iconbtn sm" title="清理旧作品" onClick={() => open('cleanup')}><Wind size={15} /></button>
        <button className="iconbtn sm" title="回收站" onClick={() => open('trash')}><Trash2 size={15} /></button>
        {!inSheet && <button className="iconbtn sm dock-close" aria-label="收起作品库" onClick={() => useStore.getState().setLibraryOpen(false)}><X size={15} /></button>}
      </div>
      <div className="lib-import-row">
        <div className="lib-search"><Search size={14} /><input type="search" value={filter.q} placeholder="搜索提示词、模型或编号" onChange={e => setFilter({ q: e.target.value })} /></div>
        <button className="btn sm" title="导入图片或视频" aria-label="导入图片或视频" disabled={importing} onClick={() => input.current?.click()}>{importing ? <span className="spinner" /> : <Upload size={14} />}导入</button>
        <input ref={input} type="file" aria-label="选择本地素材" accept="image/png,image/jpeg,image/webp,video/mp4,.mp4" hidden onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void importFile(file) }} />
      </div>
      <div className="chips lib-filters">
        <button className={cx('chip', !filter.kind && !filter.starred && 'on')} onClick={() => setFilter({ kind: '', starred: false })}>全部 {stats.all}</button>
        <button className={cx('chip', filter.kind === 'image' && 'on')} onClick={() => setFilter({ kind: 'image', starred: false })}>图片 {stats.image}</button>
        <button className={cx('chip', filter.kind === 'video' && 'on')} onClick={() => setFilter({ kind: 'video', starred: false })}>视频 {stats.video}</button>
        <button className={cx('chip', filter.starred && 'on')} onClick={() => setFilter({ starred: !filter.starred, kind: '' })}><Star size={12} />{stats.star}</button>
      </div>
      {selecting && <SelBar visible={items} />}
      <div className="lib-scroll">
        {!items.length && (
          <div className="empty"><Sparkles size={20} /><b>{rounds.length ? '没有匹配的作品' : '作品会出现在这里'}</b><span>{rounds.length ? '换个关键词或筛选条件试试。' : '生成完成后自动保存，可以收藏、复用参数或拖到参考图。'}</span></div>
        )}
        {groups.map(g => (
          <div key={g.label} className="lib-group">
            <div className="lib-date">{g.label}</div>
            <div className="lib-grid">
              {g.items.map(r => (
                <motion.button layout="position" key={r.id} className={cx('tile', viewing === r.id && 'on', selected.includes(r.id) && 'sel')}
                  draggable onDragStart={e => (e as unknown as React.DragEvent).dataTransfer.setData('text/x-round', r.id)}
                  onClick={e => onTile(r, e)} onDoubleClick={() => open('lightbox', { id: r.id })}
                  style={{ aspectRatio: `${r.width || 1} / ${r.height || 1}` }} title={r.prompt}>
                  <img src={media.thumb(r)} alt="" loading="lazy" />
                  <span className="tile-id">{rid(r.id)}</span>
                  {r.kind === 'video' && <span className="tile-kind"><Film size={11} />{r.media_duration_s != null ? `${+r.media_duration_s.toFixed(2)}s` : ''}</span>}
                  {r.starred && <span className="tile-star"><Star size={11} fill="currentColor" /></span>}
                  {selecting && <span className={cx('tile-check', selected.includes(r.id) && 'on')} />}
                </motion.button>
              ))}
            </div>
          </div>
        ))}
        {items.length > page && <button className="btn sm more" onClick={() => setPage(p => p + PAGE)}>再显示 {Math.min(PAGE, items.length - page)} 个</button>}
      </div>
    </div>
  )
}

function SelBar({ visible }: { visible: Round[] }) {
  const selected = useStore(s => s.selected)
  const rounds = useStore(s => s.rounds)
  const toast = useStore(s => s.toast)
  const open = useStore(s => s.openSheet)
  const load = useStore(s => s.loadRounds)
  const ask = useConfirm(s => s.ask)
  const n = selected.length
  const star = async (v: boolean) => { await api.star(selected, v); await load(); toast(v ? `已收藏 ${n} 个` : `已取消收藏 ${n} 个`, 'ok') }
  const del = async () => {
    const starred = selected.filter(id => rounds.find(r => r.id === id)?.starred).length
    const ok = await ask({ title: `删除 ${n} 个作品？`, body: `会移入回收站，7 天内可以恢复。${starred ? `<br><b>其中 ${starred} 个是收藏的。</b>` : ''}`, ok: '删除', danger: true })
    if (!ok) return
    const r = await api.deleteRounds(selected)
    useStore.setState({ selected: [] }); await load()
    toast(`已删除 ${r.deleted.length} 个`, 'ok', { label: '撤销', fn: async () => { await api.restore(r.deleted); await load() } })
  }
  const imgs = selected.filter(id => rounds.find(r => r.id === id)?.kind === 'image')
  return (
    <div className="selbar">
      <b className="tabular">已选 {n}</b>
      <button className="btn sm ghost" onClick={() => useStore.setState({ selected: visible.map(r => r.id) })}>全选</button>
      <button className="btn sm ghost" onClick={() => useStore.setState({ selected: [] })}>清除</button>
      <span className="grow" />
      <button className="btn sm" disabled={imgs.length !== 2} title="选两张图片" onClick={() => open('compare', { a: imgs[0], b: imgs[1] })}>对比</button>
      <button className="btn sm" disabled={!n} onClick={() => star(true)}>收藏</button>
      <button className="btn sm" disabled={!n} onClick={() => star(false)}>取消收藏</button>
      <button className="btn sm danger" disabled={!n} onClick={del}>删除</button>
      <button className="btn sm primary" onClick={() => useStore.setState({ selecting: false, selected: [] })}>完成</button>
    </div>
  )
}
