// 顶栏：品牌、工作台切换、算力状态、主题、日志、设置。
import { AnimatePresence, motion } from 'motion/react'
import { Clapperboard, Film, Image as ImageIcon, LayoutGrid, LogOut, Moon, ScrollText, Settings, Sun, Timer, Zap } from 'lucide-react'
import { api } from '../api/client'
import { useStore } from '../store/store'
import { Seg, useTick } from './Overlay'
import { cx, dur, now } from '../lib/util'
import type { Phase } from '../api/types'
import type { Workspace } from '../store/store'

const PHASE_TEXT: Record<Phase, string> = { idle: '空闲', starting: '正在拉起', ready: '就绪', generating: '生成中', stopping: '释放中', error: '出错' }
const PHASE_DOT: Record<Phase, string> = { idle: '', starting: 'busy', ready: 'ok', generating: 'busy', stopping: 'warn', error: 'bad' }

export function Topbar() {
  const st = useStore(s => s.status)
  const cfg = useStore(s => s.cfg)
  const ws = useStore(s => s.workspace)
  const setWs = useStore(s => s.setWorkspace)
  const open = useStore(s => s.openSheet)
  const theme = useStore(s => s.theme)
  const setTheme = useStore(s => s.setTheme)
  const logs = useStore(s => s.logs)
  const libOpen = useStore(s => s.libraryOpen)
  const setLibOpen = useStore(s => s.setLibraryOpen)
  const roundCount = useStore(s => s.rounds.length)
  const wfStatus = useStore(s => s.status?.workflow_active?.status)
  const wfDone = useStore(s => s.status?.workflow_active?.done_steps)
  const wfTotal = useStore(s => s.status?.workflow_active?.total_steps)
  useTick(1000)

  const statusError = useStore(s => s.statusError)
  const phase = st?.phase || 'idle'
  const holding = st?.idle_minutes === 0 && (st.active_gpu || st.colab.any_running) && !st.current
  const countdown = st?.idle_deadline && !st.current ? st.idle_deadline - now() : null
  const colab = st?.colab
  const bal = colab?.balance == null ? null : Number(colab.balance).toFixed(1)

  return (
    <header className="topbar glass">
      <div className="brand"><span className="mark"><Zap size={15} /></span>Colab Studio<small>{cfg?.version}</small></div>
      <Seg ariaLabel="工作台" value={ws} onChange={v => setWs(v as Workspace)} options={[
        { id: 'image', label: <span className="hide-sm">生图</span>, icon: <ImageIcon size={15} /> },
        { id: 'video', label: <span className="hide-sm">视频</span>, icon: <Clapperboard size={15} /> },
        { id: 'workflow', label: <span>工作流{(wfStatus === 'running' || wfStatus === 'paused') && <em className={cx('nav-badge', wfStatus === 'paused' && 'warn')} title={wfStatus === 'paused' ? '待审核' : '运行中'}>{wfStatus === 'paused' && '待审核 '}{wfDone}/{wfTotal}</em>}</span>, icon: <Film size={15} /> },
      ]} />
      <span className="status-pill" title={statusError || st?.error || ''}>
        <i className={cx('dot', statusError ? 'warn' : PHASE_DOT[phase])} />
        <span>{statusError ? '连接中断' : PHASE_TEXT[phase]}{!statusError && st?.active_gpu ? ` · ${st.active_gpu}` : ''}</span>
      </span>
      <AnimatePresence>
        {(holding || countdown != null) && (
          <motion.span className="status-pill idle" initial={{ opacity: 0, scale: .9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} title={holding ? '不会自动释放，直到手动释放' : '空闲到期自动释放'}>
            <Timer size={13} />{holding ? '保持持有' : `${dur(countdown!)} 后释放`}
          </motion.span>
        )}
      </AnimatePresence>
      <span className="grow" />
      <button className="status-pill btn-pill" onClick={() => open('settings')} title="Colab 账号与算力">
        <i className={cx('dot', !colab?.authed ? 'warn' : !colab.ok ? 'bad' : colab.any_running ? 'busy' : 'ok')} />
        <span className="hide-sm">{!colab?.authed ? '连接 Colab' : !colab.ok ? 'Colab 异常' : colab.any_running ? `${colab.sessions.length} 台 · ${Number(colab.rate_per_hour || 0).toFixed(1)} CU/h` : `余额 ${bal ?? '?'} CU`}</span>
      </button>
      {ws !== 'workflow' && (
        <button className={cx('status-pill btn-pill lib-toggle', libOpen && 'on')} onClick={() => setLibOpen(!libOpen)} title="作品库 (G)" aria-pressed={libOpen}>
          <LayoutGrid size={14} /><span className="hide-sm">作品库</span><span className="tabular dim">{roundCount}</span>
        </button>
      )}
      <button className="iconbtn" onClick={() => open('logs')} title="实时日志 (L)"><ScrollText size={16} />{logs.length > 0 && <span className="badge-dot" />}</button>
      <button className="iconbtn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title="切换亮色 / 暗色"><ThemeIcon theme={theme} /></button>
      <button className="iconbtn" onClick={() => open('settings')} title="设置"><Settings size={16} /></button>
      <button className="iconbtn" title="退出登录" onClick={async () => {
        try { await api.logout(); location.hash = 'login' }
        catch (e) { useStore.getState().toast(e instanceof Error ? e.message : '退出失败', 'err') }
      }}><LogOut size={16} /></button>
    </header>
  )
}
function ThemeIcon({ theme }: { theme: string }) {
  return theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />
}
