"use client"

import { useEffect, useState } from "react"
import ChartTile from "../../components/ChartTile"
import AppShell, { PageHeader } from "../../components/AppShell"
import { getQueryHistory, type QueryResult } from "../../lib/api"
import { PlusIcon, CloseIcon, GridIcon, ReportIcon } from "../../components/icons"

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
    <AppShell>
      <div className="mx-auto max-w-7xl px-6 py-10">
        <PageHeader
          title={
            <input
              value={dashName}
              onChange={(e) => setDashName(e.target.value)}
              className="-mx-2 rounded-lg border border-transparent bg-transparent px-2 text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 hover:border-slate-200 focus:border-brand-300 focus:bg-white focus:outline-none"
            />
          }
          subtitle="Pin saved query results into a live board."
          action={
            <div className="flex gap-2">
              <a href="/reports" className="btn-secondary">
                <ReportIcon className="h-4 w-4" /> Schedule report
              </a>
              <button onClick={() => setShowPicker(true)} className="btn-primary">
                <PlusIcon className="h-4 w-4" /> Add chart
              </button>
            </div>
          }
        />

        {tiles.length === 0 ? (
          <div className="card flex flex-col items-center justify-center gap-3 py-24 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-500">
              <GridIcon className="h-7 w-7" />
            </div>
            <p className="text-lg font-semibold text-slate-900">Your dashboard is empty</p>
            <p className="max-w-sm text-sm text-slate-500">Run a query in Ask, then pin the result here to build a board.</p>
            <button onClick={() => setShowPicker(true)} className="btn-primary mt-2">
              <PlusIcon className="h-4 w-4" /> Add a chart from history
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            {tiles.map((tile) => (
              <div key={tile.id} className="group relative">
                <button
                  onClick={() => removeTile(tile.id)}
                  className="absolute -right-2 -top-2 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 opacity-0 shadow-soft transition hover:text-rose-500 group-hover:opacity-100"
                  title="Remove tile"
                >
                  <CloseIcon className="h-4 w-4" />
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

        {/* Picker modal */}
        {showPicker && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 animate-fade-in">
            <div className="card w-full max-w-md max-h-[70vh] overflow-y-auto p-6 shadow-card animate-fade-in-up">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-900">Add chart from history</h3>
                <button onClick={() => setShowPicker(false)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
                  <CloseIcon className="h-5 w-5" />
                </button>
              </div>
              {history.length === 0 && <p className="text-sm text-slate-400">No query history yet.</p>}
              <div className="space-y-2">
                {history.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => addTile(q)}
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-left text-sm transition hover:border-brand-300 hover:bg-brand-50"
                  >
                    <div className="truncate font-medium text-slate-800">{q.natural_language}</div>
                    <div className="mt-0.5 text-xs text-slate-400">{q.chart_config?.chart_type ?? "table"} · {q.created_at?.slice(0, 10)}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
