"use client"

import { useEffect, useState } from "react"
import ChartTile from "../../components/ChartTile"
import { getQueryHistory, type QueryResult } from "../../lib/api"

export default function DashboardPage() {
  const [tiles, setTiles] = useState<QueryResult[]>([])
  const [history, setHistory] = useState<QueryResult[]>([])
  const [showPicker, setShowPicker] = useState(false)
  const [dashName, setDashName] = useState("My Dashboard")

  useEffect(() => {
    getQueryHistory().then((r) => setHistory(r.items)).catch(() => null)
    const saved = localStorage.getItem("dashboard_tiles")
    if (saved) {
      try { setTiles(JSON.parse(saved)) } catch { /* ignore */ }
    }
  }, [])

  function saveTiles(next: QueryResult[]) {
    setTiles(next)
    localStorage.setItem("dashboard_tiles", JSON.stringify(next))
  }

  function addTile(q: QueryResult) {
    if (tiles.find((t) => t.id === q.id)) return
    saveTiles([...tiles, q])
    setShowPicker(false)
  }

  function removeTile(id: string) {
    saveTiles(tiles.filter((t) => t.id !== id))
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <a href="/chat" className="text-gray-400 hover:text-gray-700 text-sm">← Chat</a>
        <input
          value={dashName}
          onChange={(e) => setDashName(e.target.value)}
          className="font-semibold text-lg border-none outline-none flex-1"
        />
        <button
          onClick={() => setShowPicker(true)}
          className="bg-gray-900 text-white text-sm rounded-lg px-4 py-1.5"
        >
          + Add chart
        </button>
        <a href="/reports" className="text-sm border border-gray-200 rounded-lg px-4 py-1.5 hover:bg-gray-50">
          Schedule report
        </a>
      </header>

      {/* Grid */}
      <div className="p-6">
        {tiles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-96 text-gray-400">
            <p className="text-lg font-medium mb-2">Your dashboard is empty</p>
            <p className="text-sm mb-4">Run a query in Chat, then add charts here.</p>
            <button onClick={() => setShowPicker(true)} className="text-sm text-blue-600 hover:underline">
              Add a chart from history
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {tiles.map((tile) => (
              <div key={tile.id} className="relative">
                <button
                  onClick={() => removeTile(tile.id)}
                  className="absolute top-2 right-2 z-10 text-gray-400 hover:text-red-500 text-lg leading-none"
                >
                  ×
                </button>
                <ChartTile
                  chartConfig={tile.chart_config ?? null}
                  data={tile.result_cache ?? []}
                  narrative={tile.narrative ?? null}
                  isLoading={false}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Picker modal */}
      {showPicker && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full max-h-[70vh] overflow-y-auto">
            <div className="flex justify-between mb-4">
              <h3 className="font-semibold text-lg">Add chart from history</h3>
              <button onClick={() => setShowPicker(false)} className="text-gray-400 hover:text-gray-700">✕</button>
            </div>
            {history.length === 0 && <p className="text-sm text-gray-400">No query history yet.</p>}
            <div className="space-y-2">
              {history.map((q) => (
                <button
                  key={q.id}
                  onClick={() => addTile(q)}
                  className="w-full text-left border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50 text-sm"
                >
                  <div className="font-medium truncate">{q.natural_language}</div>
                  <div className="text-xs text-gray-400">{q.chart_config?.chart_type ?? "table"} · {q.created_at?.slice(0, 10)}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
