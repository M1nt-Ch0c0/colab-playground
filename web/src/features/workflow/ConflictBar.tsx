import { CircleAlert } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { expand, instant } from '../../ui/motion'
import { AGENT_COPY as C } from './agentCopy'

export type ConflictKind =
  | { kind: 'changed' | 'expired' | 'stale' }
  | { kind: 'shots'; nums: readonly number[] }
  | { kind: 'partial'; applied: number; nums: readonly number[] }

export function ConflictBar({ conflict, onRegenerate, onKeep, disabled }: {
  conflict: ConflictKind; onRegenerate: () => void; onKeep: () => void; disabled?: boolean
}) {
  const reduce = useReducedMotion()
  const stale = conflict.kind === 'stale'
  const message = conflict.kind === 'shots' ? C.conflict.shots(conflict.nums)
    : conflict.kind === 'partial' ? C.conflict.partial(conflict.applied, conflict.nums)
      : conflict.kind === 'expired' ? C.proposal.state.expired : stale ? C.agent.stale.text : C.conflict.changed
  const transition = reduce ? instant : expand
  return <motion.div className="conflict-bar" role="status"
    initial={reduce ? false : { height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
    exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }} transition={transition}>
    <motion.div className="warnbox" initial={reduce ? false : { y: -4 }} animate={{ y: 0 }} transition={transition}>
      <CircleAlert size={14} /><span className="grow">{message}</span>
      <div className="conflict-actions">
        <button className="btn sm primary" onClick={onRegenerate} disabled={disabled}>
          {stale ? C.agent.stale.resend : C.conflict.regenerate}
        </button>
        <button className="btn sm ghost" onClick={onKeep} disabled={disabled}>
          {stale ? C.agent.stale.dismiss : C.conflict.keep}
        </button>
      </div>
    </motion.div>
  </motion.div>
}
