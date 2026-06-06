"use client"

import { useEffect, useRef, useState } from "react"
import { createAgentSocket, submitQuery, type AgentEvent, type QueryResult } from "../lib/api"
import AgentTrace from "./AgentTrace"
import ChartTile from "./ChartTile"

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
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-4">
            <p className="text-lg font-medium">Ask a question about your data</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {["Show me total revenue by month", "Top 10 customers by order count", "Compare sales this week vs last week"].map((s) => (
                <button key={s} onClick={() => { setInput(s) }}
                  className="text-sm border border-gray-200 rounded-full px-3 py-1 hover:bg-gray-50">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "user" ? (
              <div className="bg-gray-900 text-white rounded-2xl rounded-tr-sm px-4 py-2 max-w-md text-sm">
                {msg.text}
              </div>
            ) : (
              <div className="max-w-2xl w-full">
                {msg.loading && (
                  <AgentTrace clientId={clientId} events={msg.events ?? []} />
                )}
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
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-700">
                    {msg.text}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-gray-200 bg-white px-6 py-4">
        <div className="flex gap-3 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
            placeholder="Ask a question… (Cmd+Enter to send)"
            className="flex-1 border border-gray-200 rounded-xl px-4 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-gray-900"
          />
          <button
            onClick={sendQuery}
            disabled={running || !input.trim()}
            className="bg-gray-900 text-white rounded-xl px-5 py-2 text-sm font-semibold hover:bg-gray-700 disabled:opacity-40 transition"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
