"use client"

import { useEffect, useState } from "react"
import type { AgentEvent } from "../lib/api"

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
  const completedAt = isComplete ? events.find((e) => e.event === "pipeline_complete") : null

  function getStepStatus(key: string): StepStatus {
    return stepStates[key]?.status ?? "idle"
  }

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-4 text-sm">
      <div className="space-y-2">
        {STEPS.map((step, i) => {
          const status = getStepStatus(step.key)
          const preview = stepStates[step.key]?.preview

          return (
            <div key={step.key} className="flex items-start gap-3">
              {/* Status icon */}
              <div className="mt-0.5 shrink-0">
                {status === "idle" && (
                  <div className="w-5 h-5 rounded-full border-2 border-gray-200" />
                )}
                {status === "active" && (
                  <div className="w-5 h-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                )}
                {status === "complete" && (
                  <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                {status === "error" && (
                  <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center text-white text-xs font-bold">✕</div>
                )}
              </div>

              <div>
                <p className={`font-medium leading-5 ${status === "active" ? "text-blue-700" : status === "complete" ? "text-gray-900" : "text-gray-400"}`}>
                  {step.label}
                </p>
                {status === "active" && <p className="text-xs text-gray-400">{step.desc}</p>}
                {status === "complete" && preview && <p className="text-xs text-gray-500">{preview}</p>}
                {status === "error" && <p className="text-xs text-red-500">Failed</p>}
              </div>
            </div>
          )
        })}
      </div>

      {isComplete && (
        <p className="mt-3 text-xs text-green-600 font-medium border-t border-gray-100 pt-2">
          Pipeline complete
        </p>
      )}
      {hasError && !isComplete && (
        <p className="mt-3 text-xs text-red-600 font-medium border-t border-gray-100 pt-2">
          Pipeline failed
        </p>
      )}
    </div>
  )
}
