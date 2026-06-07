"use client"

import { useEffect, useState } from "react"
import type { AgentEvent } from "../lib/api"
import { SparkleIcon, CheckIcon, CloseIcon } from "./icons"

const STEPS = [
  { key: "query_writer", label: "Query Writer", desc: "Generating SQL…" },
  { key: "sql_executor", label: "SQL Executor", desc: "Running query…" },
  { key: "data_analyst", label: "Data Analyst", desc: "Analyzing results…" },
  { key: "chart_selector", label: "Chart Selector", desc: "Choosing visualization…" },
  { key: "narrative", label: "Narrative", desc: "Writing commentary…" },
]

type StepStatus = "idle" | "active" | "complete" | "error"

interface StepState {
  status: StepStatus
  preview?: string
}

function buildStepStates(events: AgentEvent[]): Record<string, StepState> {
  const states: Record<string, StepState> = {}
  for (const e of events) {
    const node = (e as { node?: string }).node ?? ""
    if (e.event === "node_start") {
      states[node] = { status: "active" }
    } else if (e.event === "node_complete") {
      const payload = (e as { payload?: Record<string, unknown> }).payload ?? {}
      const preview = payload.sql
        ? `SQL generated`
        : payload.rows !== undefined
        ? `${payload.rows} rows returned`
        : payload.summary
        ? String(payload.summary)
        : payload.chart_type
        ? `Chart: ${payload.chart_type}`
        : payload.headline
        ? String(payload.headline)
        : ""
      states[node] = { status: "complete", preview }
    } else if (e.event === "node_error") {
      states[node] = { status: "error" }
    }
  }
  return states
}

interface Props {
  clientId: string
  /** Pass pre-collected events when embedding inside ChatPanel */
  events?: AgentEvent[]
}

export default function AgentTrace({ clientId, events: externalEvents }: Props) {
  const [internalEvents, setInternalEvents] = useState<AgentEvent[]>([])

  // If no external events are provided, connect to WS directly (standalone mode)
  useEffect(() => {
    if (externalEvents !== undefined) return
    const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000") + "/ws/" + clientId
    const ws = new WebSocket(wsUrl)
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as AgentEvent
        setInternalEvents((s) => [...s, data])
      } catch {
        // ignore
      }
    }
    return () => ws.close()
  }, [clientId, externalEvents])

  const events = externalEvents ?? internalEvents
  const stepStates = buildStepStates(events)
  const isComplete = events.some((e) => e.event === "pipeline_complete")
  const hasError = events.some((e) => e.event === "pipeline_error")

  // Elapsed time from first event to the terminal event.
  let elapsed: string | null = null
  if (events.length > 1) {
    const first = Date.parse(events[0]?.timestamp ?? "")
    const last = Date.parse(events[events.length - 1]?.timestamp ?? "")
    if (!Number.isNaN(first) && !Number.isNaN(last) && last >= first) {
      elapsed = `${((last - first) / 1000).toFixed(1)}s`
    }
  }

  function getStepStatus(key: string): StepStatus {
    return stepStates[key]?.status ?? "idle"
  }

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/60 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <SparkleIcon className="h-4 w-4 text-brand-500" />
          <span className="text-sm font-semibold text-slate-700">AI pipeline</span>
        </div>
        {isComplete ? (
          <span className="badge bg-emerald-50 text-emerald-700">Complete{elapsed ? ` · ${elapsed}` : ""}</span>
        ) : hasError ? (
          <span className="badge bg-rose-50 text-rose-700">Failed</span>
        ) : (
          <span className="badge bg-brand-50 text-brand-700">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" /> Running
          </span>
        )}
      </div>

      {/* Steps */}
      <div className="relative p-4">
        {/* connecting line */}
        <div className="absolute left-[30px] top-7 bottom-7 w-px bg-slate-100" />
        <div className="space-y-1">
          {STEPS.map((step) => {
            const status = getStepStatus(step.key)
            const preview = stepStates[step.key]?.preview
            return (
              <div key={step.key} className="relative flex items-start gap-3 rounded-lg px-1 py-1.5">
                <div className="z-10 mt-0.5 shrink-0">
                  {status === "idle" && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-slate-200 bg-white" />
                  )}
                  {status === "active" && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-white">
                      <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
                    </div>
                  )}
                  {status === "complete" && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-gradient text-white shadow-sm">
                      <CheckIcon className="h-3.5 w-3.5" strokeWidth={3} />
                    </div>
                  )}
                  {status === "error" && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-500 text-white">
                      <CloseIcon className="h-3.5 w-3.5" strokeWidth={3} />
                    </div>
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm font-medium leading-6 ${
                      status === "active"
                        ? "text-brand-700"
                        : status === "complete"
                        ? "text-slate-900"
                        : status === "error"
                        ? "text-rose-600"
                        : "text-slate-400"
                    }`}
                  >
                    {step.label}
                  </p>
                  {status === "active" && <p className="text-xs text-slate-400">{step.desc}</p>}
                  {status === "complete" && preview && (
                    <p className="truncate text-xs text-slate-500">{preview}</p>
                  )}
                  {status === "error" && <p className="text-xs text-rose-500">Failed</p>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
