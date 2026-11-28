// 弹层、抽屉、确认框、轻提示。全部走 spring，reduced-motion 时退化为瞬间切换。
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { create } from 'zustand'
import { cx } from '../lib/util'
import { fade, instant, spring } from './motion'

export function Scrim({ onClose, children, align = 'center' }: { onClose: () => void; children: ReactNode; align?: 'center' | 'end' }) {
  const reduce = useReducedMotion()
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <motion.div className={cx('scrim', align)} onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}
      initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={reduce ? instant : fade}>
      {children}
    </motion.div>
  )
}

export function Modal({ title, icon, onClose, children, foot, wide }: { title: string; icon?: ReactNode; onClose: () => void; children: ReactNode; foot?: ReactNode; wide?: boolean }) {
  const reduce = useReducedMotion()
  return (
    <Scrim onClose={onClose}>
      <motion.div className={cx('modal glass', wide && 'wide')} role="dialog" aria-modal="true" aria-label={title}
        initial={reduce ? false : { opacity: 0, scale: 0.96, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.98, y: 6 }}
        transition={reduce ? instant : spring}>
        <header className="mh"><span className="mh-ic">{icon}</span><h3>{title}</h3><span className="grow" /><button className="iconbtn" onClick={onClose} aria-label="关闭"><X size={16} /></button></header>
        <div className="mb">{children}</div>
        {foot && <footer className="mf">{foot}</footer>}
      </motion.div>
    </Scrim>
  )
}

export function Drawer({ title, icon, onClose, children }: { title: string; icon?: ReactNode; onClose: () => void; children: ReactNode }) {
  const reduce = useReducedMotion()
  return (
    <Scrim onClose={onClose} align="end">
      <motion.aside className="drawer glass" role="dialog" aria-modal="true" aria-label={title}
        initial={reduce ? false : { x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={reduce ? { opacity: 0 } : { x: 30, opacity: 0 }}
        transition={reduce ? instant : spring}>
        <header className="mh"><span className="mh-ic">{icon}</span><h3>{title}</h3><span className="grow" /><button className="iconbtn" onClick={onClose} aria-label="关闭"><X size={16} /></button></header>
        <div className="mb">{children}</div>
      </motion.aside>
    </Scrim>
  )
}

/* 确认框：命令式调用，返回 Promise<boolean> */
interface ConfirmState { open: boolean; title: string; body: string; ok: string; danger: boolean; resolve?: (v: boolean) => void }
export const useConfirm = create<ConfirmState & { ask: (o: Partial<ConfirmState>) => Promise<boolean>; answer: (v: boolean) => void }>(set => ({
  open: false, title: '', body: '', ok: '确定', danger: false,
  ask: o => new Promise(resolve => set({ open: true, title: o.title || '确认？', body: o.body || '', ok: o.ok || '确定', danger: !!o.danger, resolve })),
  answer: v => set(s => { s.resolve?.(v); return { open: false } }),
}))
export function ConfirmHost() {
  const c = useConfirm()
  return (
    <AnimatePresence>
      {c.open && (
        <Modal title={c.title} onClose={() => c.answer(false)}
          foot={<><button className="btn" onClick={() => c.answer(false)}>取消</button><button className={cx('btn', c.danger ? 'solid-danger' : 'primary')} onClick={() => c.answer(true)}>{c.ok}</button></>}>
          <p className="confirm-body" dangerouslySetInnerHTML={{ __html: c.body }} />
        </Modal>
      )}
    </AnimatePresence>
  )
}

export function Seg<T extends string>({ value, onChange, options, ariaLabel }: { value: T; onChange: (v: T) => void; options: { id: T; label: ReactNode; icon?: ReactNode }[]; ariaLabel: string }) {
  const reduce = useReducedMotion()
  return (
    <div className="seg" role="tablist" aria-label={ariaLabel}>
      {options.map(o => (
        <button key={o.id} role="tab" aria-selected={value === o.id} className={cx(value === o.id && 'on')} onClick={() => onChange(o.id)}>
          {value === o.id && <motion.span layoutId={'seg-' + ariaLabel} className="seg-bg" transition={reduce ? instant : spring} />}
          <span className="seg-label">{o.icon}{o.label}</span>
        </button>
      ))}
    </div>
  )
}

export function Slider({ min, max, step = 1, value, onChange, suffix }: { min: number; max: number; step?: number; value: number; onChange: (v: number) => void; suffix?: string }) {
  return (
    <div className="slider">
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} />
      <input type="number" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} />
      {suffix && <span className="dim suf">{suffix}</span>}
    </div>
  )
}

export function Field({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return <label className="field"><span className="fl">{label}{hint && <span className="dim">{hint}</span>}</span>{children}</label>
}

export function Toggle({ on, onChange, children, title, disabled }: { on: boolean; onChange: (v: boolean) => void; children: ReactNode; title?: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={on} disabled={disabled} className={cx('switch', on && 'on')} onClick={() => onChange(!on)} title={title}>
      <span className="knob" />{children}
    </button>
  )
}

export function Empty({ icon, title, text, action }: { icon: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return <div className="empty-state">{icon}<h3>{title}</h3>{text && <p>{text}</p>}{action}</div>
}

export function useTick(ms = 1000) {
  const [t, setT] = useState(0)
  useEffect(() => { const id = setInterval(() => setT(v => v + 1), ms); return () => clearInterval(id) }, [ms])
  return t
}
