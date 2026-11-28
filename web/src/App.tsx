import { AnimatePresence, motion } from 'motion/react'
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { selectPollInterval, useStore } from './store/store'
import { Topbar } from './ui/Topbar'
import { ConfirmHost } from './ui/Overlay'
import { Composer } from './features/studio/Composer'
import { Stage } from './features/studio/Stage'
import { Library } from './features/library/Library'
import { MediaEditor } from './features/library/MediaEditor'
import { CleanupSheet, CompareSheet, LibrarySheet, Lightbox, PickerSheet, TrashSheet } from './features/library/Sheets'
import { SettingsSheet } from './features/settings/Settings'
import { LogsSheet } from './features/console/Logs'
import { WorkflowWorkspace } from './features/workflow/Workflow'
import { Login } from './features/login/Login'
import { api } from './api/client'
import { cx } from './lib/util'

export function App() {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => { const f = () => setHash(location.hash); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  if (hash === '#login') return <Login />
  return <Studio />
}

function Studio() {
  const booted = useStore(s => s.booted)
  const bootError = useStore(s => s.bootError)
  const boot = useStore(s => s.boot)
  const pollInterval = useStore(selectPollInterval)
  const ws = useStore(s => s.workspace)
  const sheet = useStore(s => s.sheet)
  const libOpen = useStore(s => s.libraryOpen)
  const roundsReady = useStore(s => s.roundsRev >= 0)

  useEffect(() => { boot() }, [boot])
  useEffect(() => {
    if (!roundsReady) return
    const url = new URL(location.href)
    const tool = url.searchParams.get('tool'), id = url.searchParams.get('round')
    if ((tool !== 'mask' && tool !== 'crop' && tool !== 'clip') || !id) return
    const s = useStore.getState()
    const kind = tool === 'clip' ? 'video' : 'image'
    if (s.rounds.some(r => r.id === id && r.kind === kind)) {
      s.setWorkspace(kind)
      s.setViewing(id); s.openSheet(tool, { id })
    } else s.toast('素材已移除或类型不匹配', 'err')
    url.searchParams.delete('tool'); url.searchParams.delete('round')
    history.replaceState(history.state, '', url)
  }, [roundsReady])
  useEffect(() => {
    if (!booted) return
    let active = true
    let timer: number
    const schedule = () => {
      timer = window.setTimeout(async () => {
        await useStore.getState().refresh()
        if (active) schedule()
      }, document.hidden ? 10000 : pollInterval)
    }
    schedule()
    return () => { active = false; clearTimeout(timer) }
  }, [booted, pollInterval])
  useShortcuts()
  usePasteUpload()

  if (bootError) return <div className="boot"><b>连不上服务</b><span className="dim">{bootError}</span><button className="btn" onClick={() => location.reload()}>重试</button></div>
  if (!booted) return <div className="boot"><span className="spinner" /></div>

  return (
    <div className="app">
      <Topbar />
      <AnimatePresence mode="wait" initial={false}>
        <motion.main key={ws === 'workflow' ? 'wf' : 'studio'} className={cx('workspace', ws === 'workflow' && 'is-wf')}
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }}>
          {ws === 'workflow' ? <WorkflowWorkspace /> : (
            <>
              <Composer />
              <Stage />
              <AnimatePresence initial={false}>
                {libOpen && (
                  <motion.aside key="lib" className="lib-dock glass" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 24 }}
                    transition={{ type: 'spring', stiffness: 380, damping: 34 }}>
                    <Library />
                  </motion.aside>
                )}
              </AnimatePresence>
            </>
          )}
        </motion.main>
      </AnimatePresence>
      <AnimatePresence>
        {sheet === 'settings' && <SettingsSheet key="settings" />}
        {sheet === 'logs' && <LogsSheet key="logs" />}
        {sheet === 'library' && <LibrarySheet key="library" />}
        {sheet === 'trash' && <TrashSheet key="trash" />}
        {sheet === 'cleanup' && <CleanupSheet key="cleanup" />}
        {sheet === 'compare' && <CompareSheet key="compare" />}
        {sheet === 'picker' && <PickerSheet key="picker" />}
        {sheet === 'lightbox' && <Lightbox key="lightbox" />}
        {(sheet === 'mask' || sheet === 'crop' || sheet === 'clip') && <MediaEditor key={sheet} mode={sheet} />}
      </AnimatePresence>
      <ConfirmHost />
      <Toasts />
    </div>
  )
}

function Toasts() {
  const toasts = useStore(s => s.toasts)
  const dismiss = useStore(s => s.dismissToast)
  return (
    <div className="toasts" aria-live="polite">
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div key={t.id} layout="position" className={cx('toast glass', t.kind)} initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}>
            <i className={cx('dot', t.kind === 'ok' ? 'ok' : t.kind === 'err' ? 'bad' : '')} />
            <span>{t.text}</span>
            {t.undo && <button className="undo" onClick={() => { t.undo!.fn(); dismiss(t.id) }}>{t.undo.label}</button>}
            {t.kind === 'err' && <button className="iconbtn" aria-label="关闭提示" onClick={() => dismiss(t.id)}><X size={14} /></button>}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

/** 与旧版一致的快捷键：⌘/Ctrl+Enter 生成，←/→ 切换，S 收藏，D 下载，F 全屏，Delete 删除，L 日志，Esc 退出多选 */
function useShortcuts() {
  useEffect(() => {
    const onKey = async (e: KeyboardEvent) => {
      const s = useStore.getState()
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { if (!s.sheet && s.workspace !== 'workflow') { e.preventDefault(); s.generate() } return }
      if ((e.target as HTMLElement).matches('input,textarea,select') || s.sheet) return
      const vis = s.rounds.filter(r => (!s.galleryFilter.kind || r.kind === s.galleryFilter.kind) && (!s.galleryFilter.starred || r.starred))
      const cur = s.rounds.find(r => r.id === s.viewing)
      if (e.key === 'Escape') { if (s.selecting) useStore.setState({ selecting: false, selected: [] }); else s.setViewing(null); return }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        if (!vis.length) return
        const i = vis.findIndex(r => r.id === s.viewing)
        const d = e.key === 'ArrowLeft' ? -1 : 1
        s.setViewing(vis[i < 0 ? 0 : (i + d + vis.length) % vis.length].id); return
      }
      const k = e.key.toLowerCase()
      if (k === 'l') { s.openSheet('logs'); return }
      if (k === 'g' && s.workspace !== 'workflow') { s.setLibraryOpen(!s.libraryOpen); return }
      if (!cur) return
      if (k === 's') { await api.star([cur.id], !cur.starred); s.loadRounds() }
      else if (k === 'f') s.openSheet('lightbox', { id: cur.id })
      else if (k === 'd') { const a = document.querySelector<HTMLAnchorElement>('.actionbar a[download]'); a?.click() }
      else if (e.key === 'Delete' || e.key === 'Backspace') (document.querySelector('.actionbar .btn.danger') as HTMLButtonElement | null)?.click()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
}

/** 在创作台粘贴图片即上传为参考图 */
function usePasteUpload() {
  useEffect(() => {
    const onPaste = async (e: ClipboardEvent) => {
      const s = useStore.getState()
      if (s.workspace === 'workflow' || s.sheet) return
      const f = [...(e.clipboardData?.files || [])].find(x => /^image\/(png|jpeg|webp)$/.test(x.type))
      if (!f) return
      e.preventDefault()
      try {
        const keyframe = s.workspace === 'video' && s.draft.workflow === 'fl2va'
        const r = await api.uploadRef(f, 'first', !keyframe && !!s.status?.references.items.length)
        const st = useStore.getState().status
        if (st) useStore.setState({ status: { ...st, references: r.references } })
        if (s.workspace === 'image') s.patchDraft({ useRef: true, chain: false })
        if (keyframe) s.patchDraft({ useFirstFrame: true })
        s.toast(keyframe ? '已粘贴为首帧' : '已粘贴为参考图', 'ok')
      } catch (err) { s.toast(err instanceof Error ? err.message : '上传失败', 'err') }
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [])
}
