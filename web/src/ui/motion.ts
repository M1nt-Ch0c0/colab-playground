import type { Transition } from 'motion/react'

export const EASE = [0.32, 0.72, 0, 1] as const

export const spring: Transition = { type: 'spring', stiffness: 420, damping: 34, mass: 0.8 }
export const springSmall: Transition = { type: 'spring', stiffness: 560, damping: 40, mass: 0.6 }
export const expand: Transition = { duration: 0.26, ease: EASE }
export const fade: Transition = { duration: 0.18, ease: EASE }
export const quick: Transition = { duration: 0.14, ease: EASE }
export const instant: Transition = { duration: 0 }
