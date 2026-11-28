import { CircleAlert, Film, ImageIcon, RefreshCw, RotateCcw } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { Operation, OperationItem } from '../../api/types'
import { useStore } from '../../store/store'
import { expand, fade, instant, quick, spring, springSmall } from '../../ui/motion'
import { AGENT_COPY as C, errorCopy, framesLabel, sizeLabel } from './agentCopy'

const copy = C.operation
const tones: Record<Operation['state'], string> = {
  awaiting_approval: 'run', queued: '', running: 'run', partial: 'warn', done: 'ok', failed: 'bad', canceled: '', unknown: '',
}
export const operationActive = (state: Operation['state']) => state === 'queued' || state === 'running'
export const operationReconciling = (op: Operation) => op.state === 'unknown' || op.items.some(item => item.state === 'unknown')

export function OperationCard({ operation, update, disabled, animateEntry = true, reconciling = true, onRefresh }: {
  operation: Operation; update: (op: Operation) => void; disabled?: boolean; animateEntry?: boolean
  reconciling?: boolean; onRefresh?: () => void
}) {
  const reduce = useReducedMotion()
  const { operation_id: id, state, kind, done, total, items } = operation
  const titleId = useId()
  const [busy, setBusy] = useState<'approve' | 'cancel' | 'retry' | string>()
  const [width, setWidth] = useState<number>()
  const [computeBlocked, setComputeBlocked] = useState(false)
  const seenFailed = useRef(new Map<string, OperationItem>())
  const authed = useStore(s => s.status?.colab.authed)
  const needsCompute = state === 'awaiting_approval' && (authed === false || operation.needs_compute || (computeBlocked && authed !== true))
  useEffect(() => {
    if (computeBlocked && authed === true && !operation.needs_compute) setComputeBlocked(false)
  }, [computeBlocked, authed, operation.needs_compute])
  const locked = disabled || !!busy
  const media = operation.results.length ? operation.results : operation.references
  const failures = items.filter(item => item.state === 'failed')
  for (const item of items) {
    if (item.state === 'failed') seenFailed.current.set(item.item_key, item)
    else if (item.state !== 'queued' && item.state !== 'running') seenFailed.current.delete(item.item_key)
  }
  const visibleFailures = items.filter(item => seenFailed.current.has(item.item_key))
  const hasUnknown = items.some(item => item.state === 'unknown')
  const canCancel = state === 'awaiting_approval' || state === 'queued' || state === 'running'
    || (hasUnknown && !(failures.length > 0 && operation.results.length > 0))
  const canConfirm = state === 'awaiting_approval'
  const canRetry = (state === 'failed' || state === 'partial' || state === 'unknown') && failures.length > 0
  const canView = (state === 'done' || state === 'partial') && operation.results.length > 0
  const hasFooter = canCancel || canConfirm || canRetry || canView
  const Icon = kind === 'video' ? Film : ImageIcon

  async function act(action: 'approve' | 'cancel' | 'retry', item?: string) {
    if (locked) return
    setBusy(item ?? action)
    const store = useStore.getState()
    try {
      const next = action === 'approve' ? await api.wf.approveOperation(id)
        : action === 'cancel' ? await api.wf.cancelOperation(id)
          : await api.wf.retryOperation(id, item ? [item] : undefined)
      update(next)
      if (action === 'approve' && operationActive(next.state)) store.toast(C.toast.queued, 'ok')
      if (action === 'approve') setComputeBlocked(false)
      void store.refresh()
    } catch (error) {
      const code = error instanceof ApiError ? error.code : undefined
      if (action === 'approve' && code === 'colab_unauthed') { setComputeBlocked(true); void store.refresh() }
      else store.toast(errorCopy(code).text, 'err')
    } finally { setBusy(undefined) }
  }
  async function view() {
    const store = useStore.getState()
    const round = operation.results[0]
    if (!round) return
    await store.loadRounds()
    store.openSheet('lightbox', { id: round.id })
  }

  return <motion.article className="op-card" data-state={state}
    initial={reduce || !animateEntry ? false : { opacity: 0, y: 8, scale: .985 }}
    animate={{ opacity: 1, y: 0, scale: 1 }} transition={reduce ? instant : spring}>
    <header className="op-h">
      <Icon size={15} /><b id={titleId}>{copy.title[kind](total)}</b><span className="grow" />
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span className={`tag ${tones[state]}`} key={state} initial={reduce ? false : { opacity: 0, y: 3 }}
          animate={{ opacity: 1, y: 0 }} exit={reduce ? { opacity: 0 } : { opacity: 0, y: -3 }} transition={reduce ? instant : quick}>
          {state === 'unknown' && reconciling && <span className="spinner" />}{copy.state[state]}
        </motion.span>
      </AnimatePresence>
      {hasUnknown && !reconciling && onRefresh && <button className="iconbtn sm" aria-label={copy.refresh}
        disabled={locked} onClick={onRefresh}><RefreshCw size={13} /></button>}
    </header>
    <p className="op-meta"><span data-user-content>{operation.model}</span>{' · '}{sizeLabel(operation.width, operation.height)}
      {operation.num_frames ? ` · ${framesLabel(operation.num_frames)}` : ''}</p>
    {media.length > 0 && <div className="proposal-refs" aria-label={operation.results.length ? copy.view : C.proposal.refsAria(media.length)}>
      {media.slice(0, 4).map((ref, i) => <motion.img key={ref.id} src={ref.thumb} alt={C.proposal.refAlt(ref.label || C.board.refs)}
        data-user-content initial={reduce || !operation.results.length || !animateEntry ? false : { opacity: 0, scale: .96 }}
        animate={{ opacity: 1, scale: 1 }} transition={reduce ? instant : { ...springSmall, delay: i * .04 }} />)}
      {media.length > 4 && <span>{C.proposal.moreRefs(media.length - 4)}</span>}
    </div>}
    {(state === 'queued' || state === 'running' || state === 'partial') && <div className="op-progress">
      <div className={`bar thin${state === 'queued' ? ' indet' : ''}`} role="progressbar" aria-labelledby={titleId}
        aria-valuemin={state === 'queued' ? undefined : 0}
        aria-valuemax={state === 'queued' ? undefined : total}
        aria-valuenow={state === 'queued' ? undefined : done}
        aria-valuetext={state === 'queued' ? copy.state.queued : copy.progress(done, total)}>
        <i style={state === 'queued' ? undefined : { width: `${done / total * 100}%` }} />
      </div>
      <span className="tabular">{copy.progress(done, total)}</span>
    </div>}
    <ul className="op-items">
      <AnimatePresence initial={false}>
        {visibleFailures.slice(0, 3).map(item => <motion.li key={item.item_key} layout={reduce ? false : 'position'}
          initial={false} exit={reduce ? { opacity: 0 } : { opacity: 0, height: 0, transition: expand }}
          transition={reduce ? instant : spring}>
          <div className="op-item">
            <span>{copy.item(item.seq)}</span>
            <AnimatePresence mode="wait" initial={false}>
              <motion.span className="op-item-error grow" key={item.error_code ?? seenFailed.current.get(item.item_key)?.error_code}
                initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={reduce ? instant : quick}>
                {errorCopy(item.error_code ?? seenFailed.current.get(item.item_key)?.error_code).text}
              </motion.span>
            </AnimatePresence>
            <button className="iconbtn sm" aria-label={copy.retryItem} disabled={locked || item.state !== 'failed'}
              onClick={() => void act('retry', item.item_key)}>
              {busy === item.item_key || item.state !== 'failed' ? <span className="spinner" /> : <RotateCcw size={14} />}
            </button>
          </div>
        </motion.li>)}
      </AnimatePresence>
      {visibleFailures.length > 3 && <li className="op-more">{copy.moreItems(visibleFailures.length - 3)}</li>}
    </ul>
    {needsCompute && <div className="warnbox"><CircleAlert size={14} /><span className="grow">{copy.needsCompute}</span>
      <button className="btn sm" onClick={() => useStore.getState().openSheet('settings')}>{copy.connect}</button>
    </div>}
    <AnimatePresence mode="wait" initial={false}>
      {hasFooter && <motion.footer className="op-f" key={state}
        initial={reduce ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
        exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, transition: quick }} transition={reduce ? instant : fade}>
        {canCancel && <button className="btn sm ghost"
          disabled={locked} onClick={() => void act('cancel')}>{state === 'running' ? copy.stop : copy.cancel}</button>}
        {canConfirm && <button className="btn sm primary" disabled={locked || needsCompute}
          style={busy === 'approve' ? { minWidth: width } : undefined}
          onClick={event => { setWidth(event.currentTarget.offsetWidth); void act('approve') }}>
          <span className="proposal-spinner">{busy === 'approve' && <span className="spinner" />}</span>{copy.confirm}
        </button>}
        {canRetry && <button className="btn sm primary"
          disabled={locked} onClick={() => void act('retry')}>{busy === 'retry' && <span className="spinner" />}{copy.retryFailed(failures.length)}</button>}
        {canView && <button className="btn sm" disabled={disabled}
          onClick={() => void view()}>{copy.view}</button>}
      </motion.footer>}
    </AnimatePresence>
  </motion.article>
}
