"use client"

import { useEffect, useRef, useState } from "react"

interface Props {
  value: number
  /** Animation duration in ms. */
  duration?: number
  /** Optional formatter (e.g. compact / currency). Defaults to locale integer. */
  format?: (n: number) => string
  className?: string
}

/**
 * Counts up from 0 to `value` on mount (and whenever `value` changes) using
 * requestAnimationFrame with an ease-out curve. Respects prefers-reduced-motion
 * by snapping straight to the final value.
 */
export default function AnimatedNumber({ value, duration = 900, format, className }: Props) {
  const [display, setDisplay] = useState(0)
  const frame = useRef<number>()

  useEffect(() => {
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

    if (prefersReduced || duration <= 0) {
      setDisplay(value)
      return
    }

    const start = performance.now()
    const from = 0

    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      setDisplay(from + (value - from) * eased)
      if (t < 1) frame.current = requestAnimationFrame(tick)
      else setDisplay(value)
    }

    frame.current = requestAnimationFrame(tick)
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current)
    }
  }, [value, duration])

  const rounded = Math.round(display)
  const text = format ? format(rounded) : rounded.toLocaleString()

  return <span className={className}>{text}</span>
}

/** Compact formatter: 1.2K, 3.4M, etc. */
export function compact(n: number): string {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n)
}
