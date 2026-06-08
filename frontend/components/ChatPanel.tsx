"use client"

import { useEffect, useRef, useState } from "react"
import { createAgentSocket, submitQuery, type AgentEvent, type QueryResult } from "../lib/api"
import AgentTrace from "./AgentTrace"
import ChartTile from "./ChartTile"
import { SparkleIcon, SendIcon, BoltIcon, GridIcon, ChatIcon, ReportIcon } from "./icons"

interface Message {
  role: "user" | "assistant"
  text: string
  query?: QueryResult
  queryId?: string
  loading?: boolean
  events?: AgentEvent[]
}

interface Props {
  sourceId: string
  initialQuery?: QueryResult | null
  onQueryComplete?: (q: QueryResult) => void
}

const SUGGESTIONS = [
  { text: "Show me total revenue by month", Icon: ReportIcon },
  { text: "Top 10 customers by order count", Icon: GridIcon },
  { text: "Compare sales this week vs last week", Icon: BoltIcon },
  { text: "Which region grew the fastest?", Icon: ChatIcon },
]

export default function ChatPanel({ sourceId, initialQuery, onQueryComplete }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [clientId] = useState(() => crypto.randomUUID())
  const [running, setRunning] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load initial query from history if provided
  useEffect(() => {
    if (initialQuery) {
      setMessages([
        { role: "user", text: initialQuery.natural_language },
        { role: "assistant", text: initialQuery.natural_language, query: initialQuery },
      ])
    }
  }, [initialQuery?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // WebSocket lifecycle — connect once per clientId
  useEffect(() => {
    const ws = createAgentSocket(clientId, () => {})
    wsRef.current = ws
    return () => ws.close()
  }, [clientId])

  function appendEvent(msgIndex: number, event: AgentEvent) {
    setMessages((msgs) =>
      msgs.map((m, i) =>
        i === msgIndex ? { ...m, events: [...(m.events ?? []), event] } : m
      )
    )
  }

  async function sendQuery() {
    if (!input.trim() || running || !sourceId) return
    const question = input.trim()
    setInput("")
    setRunning(true)

    const userMsg: Message = { role: "user", text: question }
    const assistantMsg: Message = { role: "assistant", text: question, loading: true, events: [] }
    setMessages((m) => [...m, userMsg, assistantMsg])
    const assistantIndex = messages.length + 1

    // Attach event listener to ws for this query
    const ws = wsRef.current
    if (ws) {
      ws.onmessage = (ev) => {
        try {
          const event = JSON.parse(ev.data) as AgentEvent
          appendEvent(assistantIndex, event)

          if (event.event === "pipeline_complete") {
            const result = ((event as unknown) as { event: string; payload?: { result?: QueryResult } }).payload?.result
            setMessages((msgs) =>
              msgs.map((m, i) =>
                i === assistantIndex
                  ? { ...m, loading: false, query: result as QueryResult | undefined }
                  : m
              )
            )
            if (result && onQueryComplete) onQueryComplete(result as QueryResult)
            setRunning(false)
          } else if (event.event === "pipeline_error") {
            setMessages((msgs) =>
              msgs.map((m, i) =>
                i === assistantIndex
                  ? { ...m, loading: false, text: `Error: ${(event as { payload?: { error?: string } }).payload?.error ?? "unknown error"}` }
                  : m
              )
            )
            setRunning(false)
          }
        } catch {
          // ignore
        }
      }
    }

    try {
      await submitQuery({ question, source_id: sourceId, client_id: clientId })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit query"
      setMessages((msgs) =>
        msgs.map((m, i) =>
          i === assistantIndex ? { ...m, loading: false, text: `Error: ${msg}` } : m
        )
      )
      setRunning(false)
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendQuery()
  }

  return (
    <div className="flex flex-col h-full app-backdrop">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center pt-14 text-center animate-fade-in-up">
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-2xl bg-brand-gradient blur-2xl opacity-40" />
                <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow animate-float">
                  <SparkleIcon className="h-8 w-8" />
                </div>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
                What do you want to know?
              </h2>
              <p className="mt-2 max-w-md text-slate-500">
                Ask a question about your data in plain English. The agents will write
                the SQL, analyze the result, and visualize it for you.
              </p>
              <div className="mt-8 grid w-full max-w-xl grid-cols-1 gap-2.5 sm:grid-cols-2">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={s.text}
                    onClick={() => setInput(s.text)}
                    style={{ animationDelay: `${i * 70}ms` }}
                    className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-600 shadow-sm transition-all duration-200 animate-fade-in-up hover:-translate-y-0.5 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 hover:shadow-card"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500 transition-colors group-hover:bg-white">
                      <s.Icon className="h-4 w-4" />
                    </span>
                    <span className="font-medium">{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex animate-fade-in-up ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "user" ? (
                <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-brand-gradient px-4 py-2.5 text-sm font-medium text-white shadow-soft transition-transform hover:scale-[1.01]">
                  {msg.text}
                </div>
              ) : (
                <div className="flex w-full gap-3">
                  <div className="mt-0.5 hidden h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-glow sm:flex">
                    <SparkleIcon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                  {msg.loading && <AgentTrace clientId={clientId} events={msg.events ?? []} />}
                  {!msg.loading && msg.query && (
                    <ChartTile
                      chartConfig={msg.query.chart_config ?? null}
                      data={msg.query.result_cache ?? []}
                      narrative={msg.query.narrative ?? null}
                      isLoading={false}
                      sql={msg.query.generated_sql}
                    />
                  )}
                  {!msg.loading && !msg.query && (
                    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                      {msg.text}
                    </div>
                  )}
                  </div>
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="glass border-t px-4 sm:px-8 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-soft transition-all hover:shadow-card focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-500/20">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              rows={1}
              placeholder="Ask a question about your data…"
              className="flex-1 resize-none bg-transparent px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none max-h-40"
            />
            <button
              onClick={sendQuery}
              disabled={running || !input.trim()}
              className="btn-primary h-10 w-10 shrink-0 !px-0"
              title="Send (Cmd/Ctrl + Enter)"
            >
              {running ? (
                <span className="h-4 w-4 rounded-full border-2 border-white/70 border-t-transparent animate-spin" />
              ) : (
                <SendIcon className="h-[18px] w-[18px]" />
              )}
            </button>
          </div>
          <p className="mt-2 px-1 text-center text-xs text-slate-400">
            Press <kbd className="rounded border border-slate-200 bg-slate-50 px-1 font-sans">⌘/Ctrl</kbd> +{" "}
            <kbd className="rounded border border-slate-200 bg-slate-50 px-1 font-sans">Enter</kbd> to send
          </p>
        </div>
      </div>
    </div>
  )
}
