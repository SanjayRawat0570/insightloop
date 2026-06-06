"use client"

import { Suspense, useEffect, useState } from "react"
import ChatPanel from "../../components/ChatPanel"
import { getQueryHistory, getSources, type DataSource, type QueryResult } from "../../lib/api"

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
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b">
          <span className="font-bold text-sm">InsightLoop</span>
        </div>

        {/* Source selector */}
        <div className="p-4 border-b">
          <label className="block text-xs font-semibold text-gray-500 mb-1">Data source</label>
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="w-full text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none"
          >
            {sources.length === 0 && <option value="">No sources connected</option>}
            {sources.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          {sources.length === 0 && (
            <a href="/connect" className="text-xs text-blue-600 hover:underline mt-1 block">+ Connect a source</a>
          )}
        </div>

        {/* Query history */}
        <div className="flex-1 overflow-y-auto p-4">
          <p className="text-xs font-semibold text-gray-500 mb-2">History</p>
          {history.length === 0 && <p className="text-xs text-gray-400">No past queries</p>}
          {history.map((q) => (
            <button
              key={q.id}
              onClick={() => setActiveQuery(q)}
              className="w-full text-left text-xs text-gray-700 hover:bg-gray-50 rounded px-2 py-1.5 truncate block"
            >
              {q.natural_language}
            </button>
          ))}
        </div>

        <div className="p-4 border-t space-y-2">
          <a href="/dashboard" className="block text-xs text-gray-600 hover:text-gray-900">Dashboard →</a>
          <a href="/reports" className="block text-xs text-gray-600 hover:text-gray-900">Reports →</a>
          <a href="/connect" className="block text-xs text-gray-600 hover:text-gray-900">Sources →</a>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden">
        {selectedSource ? (
          <ChatPanel
            sourceId={selectedSource}
            initialQuery={activeQuery}
            onQueryComplete={(q) => setHistory((h) => [q, ...h])}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <p className="text-lg font-medium mb-2">No data source selected</p>
              <a href="/connect" className="text-sm text-blue-600 hover:underline">Connect a source to get started</a>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
