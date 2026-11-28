import { Check, X } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { Proposal, RunShotUpdate, ShotConflict } from '../../api/types'
import { applyAssistantComposerPrompt, assistantComposerPrompt, useStore } from '../../store/store'
import { expand, fade, instant, quick, spring } from '../../ui/motion'
import { AGENT_COPY as C, errorCopy, shotLabel, type ProposalField, type ProposalState } from './agentCopy'
import { ConflictBar, type ConflictKind } from './ConflictBar'
import { proposalDiff } from './proposalDiff'

type ShotText = { n: number; before: string; after: string }
interface ProposalCardProps {
  variant: 'panel' | 'inline'
  field: ProposalField
  shots: readonly ShotText[]
  refs: readonly { id: string; thumb: string; label: string }[]
  state: ProposalState
  conflict?: ConflictKind
  disabled?: boolean
  animateEntry?: boolean
  undoable: boolean
  onApply: () => void
  onReject: () => void
  onUndo: () => void
  onRegenerate: () => void
  onKeep: () => void
  onDismiss?: () => void
}

function DiffText({ text, variant, expanded, cap, onMeasure }: {
  text: { text: string; changed: boolean }[]; variant: 'before' | 'after'; expanded: boolean; cap: number;
  onMeasure?: (height: number) => void
}) {
  const reduce = useReducedMotion()
  const content = useRef<HTMLParagraphElement>(null)
  const [height, setHeight] = useState(0)
  useLayoutEffect(() => {
    const element = content.current
    if (!element) return
    const measure = () => { setHeight(element.offsetHeight); onMeasure?.(element.offsetHeight) }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [onMeasure])
  const Marker = variant === 'before' ? 'del' : 'ins'
  return <motion.div className="proposal-text-clip" initial={false}
    animate={{ height: expanded ? 'auto' : Math.min(height, cap) }} transition={reduce ? instant : expand}>
    <p ref={content} className={variant === 'before' ? 'proposal-before' : 'proposal-after'} style={{ whiteSpace: 'pre-wrap' }}>
      <span className="lbl">{C.proposal[variant]}</span>{' '}
      <span data-user-content>{text.map((segment, i) => segment.changed
        ? <Marker key={i}>{segment.text}</Marker> : segment.text)}</span>
    </p>
  </motion.div>
}

function ShotDiff({ shot, expanded, multiple, measureBefore, measureAfter }: {
  shot: ShotText; expanded: boolean; multiple: boolean; measureBefore?: (h: number) => void; measureAfter?: (h: number) => void
}) {
  const diff = useMemo(() => proposalDiff(shot.before, shot.after), [shot.before, shot.after])
  return <div className={multiple ? 'proposal-diff proposal-shot-text' : 'proposal-diff'}>
    {multiple && <b className="proposal-shot-label">{shotLabel(shot.n)}</b>}
    {(!multiple || expanded) && <DiffText variant="before" text={diff.before} expanded={expanded} cap={40} onMeasure={measureBefore} />}
    <DiffText variant="after" text={diff.after} expanded={expanded} cap={multiple ? 60 : 120} onMeasure={measureAfter} />
  </div>
}

export function ProposalCard({ variant, field, shots, refs, state, conflict, disabled, animateEntry = true, undoable,
  onApply, onReject, onUndo, onRegenerate, onKeep, onDismiss }: ProposalCardProps) {
  const reduce = useReducedMotion()
  const [expanded, setExpanded] = useState(false)
  const [beforeHeight, setBeforeHeight] = useState(0)
  const [afterHeight, setAfterHeight] = useState(0)
  const [applyWidth, setApplyWidth] = useState<number>()
  const multiple = shots.length > 1
  const nums = shots.map(shot => shot.n).filter(n => n > 0)
  const pending = state === 'pending' || state === 'applying'
  const applied = state === 'applied' || state === 'undoing'
  const collapsed = applied || state === 'undone' || state === 'rejected'
  const [closed, setClosed] = useState(collapsed)
  const footer = conflict ? null : pending ? 'pending' : applied ? 'applied' : state === 'expired' ? 'expired'
    : state === 'undone' && variant === 'inline' ? 'undone' : null
  const heightTransition = reduce ? instant : expand
  return <motion.article className="proposal" data-state={state} data-variant={variant}
    initial={reduce || !animateEntry ? false : { opacity: 0, y: 8, scale: .985 }}
    animate={{ opacity: state === 'rejected' ? .6 : 1, y: 0, scale: 1 }}
    exit={reduce ? { opacity: 0 } : { opacity: 0, height: 0, transition: expand }}
    transition={reduce ? instant : state === 'rejected' ? fade : spring}>
    <div className="proposal-inner">
      <header className="proposal-h">
        <b>{C.proposal.title(nums, field)}</b><span className="grow" />
        <AnimatePresence mode="popLayout" initial={false}>
          {state !== 'pending' && <motion.span key={state} className={applied ? 'tag ok' : 'tag'}
            initial={reduce ? false : { opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -3 }} transition={reduce ? instant : quick}>
            {applied && <motion.span className="proposal-check" initial={reduce || !animateEntry ? false : { scale: .5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }} transition={reduce ? instant : spring}><Check size={12} /></motion.span>}
            {C.proposal.state[state]}
          </motion.span>}
        </AnimatePresence>
      </header>
      <motion.div className="proposal-body" initial={false} animate={{ height: collapsed ? 0 : 'auto' }} transition={heightTransition}
        onAnimationComplete={() => setClosed(collapsed)} inert={collapsed}>
        {(!closed || !collapsed) && <div className="proposal-content">
          {multiple ? <AnimatePresence initial={false}>
            {(expanded ? shots : shots.slice(0, 3)).map((shot, i) => <motion.div key={shot.n} className="proposal-shot"
              initial={reduce ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, height: 0 }}
              transition={reduce ? instant : { ...expand, delay: Math.max(0, i - 3) * .03 }}>
              <ShotDiff shot={shot} expanded={expanded} multiple />
            </motion.div>)}
          </AnimatePresence> : shots[0] && <ShotDiff shot={shots[0]} expanded={expanded} multiple={false}
            measureBefore={setBeforeHeight} measureAfter={setAfterHeight} />}
          {(multiple || beforeHeight > 40 || afterHeight > 120) && <button className="mini-link proposal-expand" aria-expanded={expanded}
            onClick={() => setExpanded(value => !value)}>{expanded ? C.proposal.collapse
              : shots.length > 3 ? C.proposal.moreShots(shots.length - 3) : C.proposal.expand}</button>}
          {!!refs.length && <div className="proposal-refs" aria-label={C.proposal.refsAria(refs.length)}>
            {refs.slice(0, 4).map(ref => <img loading="lazy" key={ref.id} src={ref.thumb}
              data-user-content alt={C.proposal.refAlt(ref.label || C.board.refs)} />)}
            {refs.length > 4 && <span>{C.proposal.moreRefs(refs.length - 4)}</span>}
          </div>}
        </div>}
      </motion.div>
      <AnimatePresence initial={false}>
        {conflict && <ConflictBar key="conflict" conflict={conflict} onRegenerate={onRegenerate} onKeep={onKeep} disabled={disabled} />}
      </AnimatePresence>
      <AnimatePresence mode="wait" initial={false}>
        {footer && <motion.footer key={footer} className="proposal-f" data-controls={footer}
          initial={reduce ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, transition: quick }} transition={reduce ? instant : fade}>
          {pending && <>
            <button className="btn sm ghost" disabled={disabled || state === 'applying'} onClick={onReject}>{C.proposal.reject}</button>
            <button className="btn sm primary" disabled={disabled || state === 'applying'}
              style={state === 'applying' ? { minWidth: applyWidth } : undefined} onClick={event => {
                setApplyWidth(event.currentTarget.offsetWidth)
                onApply()
              }}><span className="proposal-spinner">{state === 'applying' && <span className="spinner" />}</span>
              {multiple ? C.proposal.applyShots(shots.length) : C.proposal.apply}</button>
          </>}
          {applied && undoable && <button className="btn sm ghost" disabled={disabled || state === 'undoing'} onClick={onUndo}>
            {state === 'undoing' && <span className="spinner" />}{C.proposal.undo}
          </button>}
          {(applied || footer === 'undone') && variant === 'inline' && onDismiss && <button className="iconbtn sm"
            aria-label={C.proposal.dismiss} onClick={onDismiss} disabled={state === 'undoing'}><X size={14} /></button>}
          {footer === 'expired' && <button className="btn sm" onClick={onRegenerate} disabled={disabled}>{C.proposal.regenerate}</button>}
        </motion.footer>}
      </AnimatePresence>
    </div>
  </motion.article>
}

function conflictNumbers(proposal: Proposal, conflicts: readonly ShotConflict[]) {
  return [...new Set(conflicts.map(item => item.n ?? proposal.before.find(shot => shot.shot_id === item.shot_id)?.n ?? 0))]
    .filter(n => n > 0).sort((a, b) => a - b)
}

export function WorkflowProposal({ proposal, variant, changed, disabled, animateEntry, beforeWrite, onChange, onUpdate,
  onDismiss, onRegenerateComposer }: {
  proposal: Proposal; variant: 'panel' | 'inline'; changed?: boolean; disabled?: boolean; animateEntry?: boolean;
  beforeWrite?: () => Promise<boolean>; onChange: (proposal: Proposal) => void;
  onUpdate: (update: RunShotUpdate, output: Record<string, unknown>) => void;
  onDismiss: () => void;
  onRegenerateComposer?: () => void;
}) {
  const toast = useStore(s => s.toast)
  const [busy, setBusy] = useState<'applying' | 'undoing' | 'other'>()
  const [status, setStatus] = useState<ConflictKind>()
  const [hideConflict, setHideConflict] = useState(false)
  const locked = disabled || !!busy
  const conflicts = proposal.target.conflicts ?? []
  const nums = conflictNumbers(proposal, conflicts)
  const partial: ConflictKind | undefined = proposal.status === 'applied' && nums.length
    ? { kind: 'partial', applied: proposal.before.length - nums.length, nums } : undefined
  const expired = proposal.status === 'expired' || (proposal.status === 'pending' && proposal.expires_at * 1000 <= Date.now())
  const conflict = hideConflict ? undefined : status ?? (expired ? { kind: 'expired' }
    : changed && proposal.status === 'pending' ? { kind: 'changed' } : partial)

  async function ready() {
    if (beforeWrite && !await beforeWrite()) {
      toast(C.agent.unsaved, 'err')
      return false
    }
    return true
  }

  function report(err: unknown) {
    toast(errorCopy(err instanceof ApiError ? err.code : undefined).text, 'err')
  }

  async function undo(id: string) {
    if (!id) return
    setBusy('undoing')
    try {
      if (!await ready()) return
      if (proposal.kind === 'composer') {
        const before = proposal.before[0]?.text, after = proposal.after[0]?.text
        const current = assistantComposerPrompt()
        if (!current || before == null || after == null
          || current.workspace !== proposal.target.workspace || current.prompt !== after) {
          toast(C.toast.undoBlocked, 'err')
          return
        }
        if (!applyAssistantComposerPrompt(current, before)) { toast(C.toast.undoBlocked, 'err'); return }
        try {
          const result = await api.wf.undoComposer(id, current)
          onChange(result.proposal)
          setStatus(undefined)
        } catch (err) {
          applyAssistantComposerPrompt({ workspace: current.workspace, prompt: before }, after)
          throw err
        }
        return
      }
      const result = await api.wf.undoShots(id)
      onChange(result.proposal ?? { ...proposal, status: 'undone' })
      setStatus(undefined)
      onUpdate(result.run_updated, result.step_output)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'shot_conflict') toast(C.toast.undoBlocked, 'err')
      else report(err)
    } finally { setBusy(undefined) }
  }

  async function apply() {
    setBusy('applying')
    try {
      if (!await ready()) return
      if (proposal.kind === 'composer') {
        const before = proposal.before[0]?.text, after = proposal.after[0]?.text
        const current = assistantComposerPrompt()
        if (!current || before == null || after == null
          || current.workspace !== proposal.target.workspace
          || (current.prompt !== before && !(proposal.status === 'applied' && current.prompt === after))) {
          setStatus({ kind: 'changed' })
          return
        }
        const wrote = current.prompt === before && applyAssistantComposerPrompt(current, after)
        try {
          const result = await api.wf.applyComposer(proposal.proposal_id, current)
          onChange(result.proposal)
          setStatus(undefined)
          const id = result.proposal.undo_id
          toast(C.toast.applied, 'ok', id ? { label: C.toast.undo, fn: () => void undo(id) } : undefined)
        } catch (err) {
          if (wrote) applyAssistantComposerPrompt({ workspace: current.workspace, prompt: after }, before)
          throw err
        }
        return
      }
      const result = await api.wf.applyProposal(proposal.proposal_id, {
        atomicity: proposal.before.length > 1 ? 'per_shot' : 'all',
      })
      if (result.proposal) onChange(result.proposal)
      setStatus(undefined)
      onUpdate(result.run_updated, result.step_output)
      if (variant === 'panel' && result.applied.length) {
        const numbers = [...new Set(result.applied.map(item => item.n))]
        const id = result.undo_id
        toast(C.toast.appliedShots(numbers), 'ok', id ? { label: C.toast.undo, fn: () => void undo(id) } : undefined)
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === 'shot_conflict') {
        const matches = Array.isArray(err.details?.conflicts) ? conflictNumbers(proposal, err.details.conflicts as ShotConflict[]) : []
        setStatus(err.details?.status === 'expired' ? { kind: 'expired' }
          : matches.length > 1 ? { kind: 'shots', nums: matches } : { kind: 'changed' })
      } else report(err)
    } finally { setBusy(undefined) }
  }

  async function reject() {
    setBusy('other')
    try {
      onChange(await api.wf.rejectProposal(proposal.proposal_id))
      setStatus(undefined)
      if (variant === 'inline') onDismiss()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'shot_conflict' && err.details?.status === 'expired') setStatus({ kind: 'expired' })
      else report(err)
    } finally { setBusy(undefined) }
  }

  async function regenerate() {
    const { run_id: runId, step_id: stepId, target } = proposal
    if (proposal.kind === 'composer') { onRegenerateComposer?.(); return }
    if (!runId || !stepId) return
    setBusy('other')
    try {
      if (!await ready()) return
      const { shots } = await api.wf.shots(runId, stepId)
      const originals = conflicts.length ? proposal.before.filter(item => conflicts.some(conflict => conflict.shot_id === item.shot_id)) : proposal.before
      const ids = originals.flatMap(item => {
        const shot = shots.find(s => s.shot_id === item.shot_id) ?? shots.find(s => s.seq === item.n)
        return shot ? [shot.shot_id] : []
      })
      if (!ids.length || ids.length !== originals.length) { toast(errorCopy('not_found').text, 'err'); return }
      const replacement = await api.wf.rewriteShots(runId, stepId, {
        shot_ids: ids, field: target.field, instruction: target.instruction, reference_round_ids: target.reference_round_ids,
      })
      onChange(replacement)
      setStatus(undefined)
    } catch (err) { report(err) }
    finally { setBusy(undefined) }
  }

  const state = busy === 'applying' || busy === 'undoing' ? busy : expired ? 'expired' : proposal.status
  return <ProposalCard variant={variant} field={proposal.target.field}
    shots={proposal.before.map((item, i) => ({ n: item.n, before: item.text, after: proposal.after[i]?.text ?? '' }))}
    refs={proposal.references_used} state={state} conflict={conflict} disabled={locked}
    undoable={!!proposal.undo_id} animateEntry={animateEntry} onApply={() => void apply()} onReject={() => void reject()}
    onUndo={() => { if (proposal.undo_id) void undo(proposal.undo_id) }}
    onRegenerate={() => void regenerate()} onDismiss={onDismiss} onKeep={() => {
      if (expired) onDismiss()
      else if (partial) setHideConflict(true)
      else void reject()
    }} />
}
