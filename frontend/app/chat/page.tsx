"use client"

import { useEffect, useState } from "react"
import ChatPanel from "../../components/ChatPanel"
import AppShell from "../../components/AppShell"
import { getQueryHistory, getSources, type DataSource, type QueryResult } from "../../lib/api"
import { DatabaseIcon, PlusIcon, ChatIcon } from "../../components/icons"

export default function ChatPage() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [selectedSource, setSelectedSource] = useState<string>("")
  const [history, setHistory] = useState<QueryResult[]>([])
  const [activeQuery, setActiveQuery] = useState<QueryResult | null>(null)

  useEffect(() => {
    getSources().then((r) => {
      setSources(r.items)
      if (r.items.length > 0) setSelectedSource(r.items[0].id)
    }).catch(() => null)
    getQueryHistory().then((r) => setHistory(r.items)).catch(() => null)
  }, [])

  return (
    <AppShell scroll={false}>
      <div className="flex h-full">
        {/* Context panel */}
        <aside className="hidden md:flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white">
          <div className="px-5 py-4 border-b border-slate-100">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Workspace</p>
            <p className="mt-0.5 font-semibold text-slate-900">Ask your data</p>
          </div>

          {/* Source selector */}
          <div className="px-5 py-4 border-b border-slate-100">
            <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-2">
              <DatabaseIcon className="h-3.5 w-3.5" /> Data source
            </label>
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="input py-2 cursor-pointer"
            >
              {sources.length === 0 && <option value="">No sources connected</option>}
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {sources.length === 0 && (
              <a href="/connect" className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700">
                <PlusIcon className="h-3.5 w-3.5" /> Connect a source
              </a>
            )}
          </div>

          {/* History */}
          <div className="flex-1 overflow-y-auto px-3 py-4">
            <p className="px-2 text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Recent</p>
            {history.length === 0 && (
              <p className="px-2 text-sm text-slate-400">No past queries yet.</p>
            )}
            <div className="space-y-1">
              {history.map((q) => {
                const active = activeQuery?.id === q.id
                return (
                  <button
                    key={q.id}
                    onClick={() => setActiveQuery(q)}
                    className={`group flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm transition ${
                      active ? "bg-brand-50 text-brand-800" : "text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <ChatIcon className={`mt-0.5 h-4 w-4 shrink-0 ${active ? "text-brand-500" : "text-slate-300 group-hover:text-slate-400"}`} />
                    <span className="truncate">{q.natural_language}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </aside>

        {/* Main */}
        <div className="flex-1 min-w-0">
          {selectedSource ? (
            <ChatPanel
              sourceId={selectedSource}
              initialQuery={activeQuery}
              onQueryComplete={(q) => setHistory((h) => [q, ...h])}
            />
          ) : (
            <div className="flex h-full items-center justify-center p-6">
              <div className="card max-w-sm p-8 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                  <DatabaseIcon className="h-6 w-6" />
                </div>
                <p className="text-lg font-semibold text-slate-900">No data source yet</p>
                <p className="mt-1 text-sm text-slate-500">Connect a source to start asking questions.</p>
                <a href="/connect" className="btn-primary mt-5 inline-flex">
                  <PlusIcon className="h-4 w-4" /> Connect a source
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
