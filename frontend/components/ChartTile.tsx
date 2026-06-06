"use client"

import { useState } from "react"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts"
import type { ChartConfig, Narrative } from "../lib/api"

const COLORS = ["#111827", "#6b7280", "#d1d5db", "#374151", "#9ca3af", "#4b5563"]

interface Props {
  chartConfig: ChartConfig | null
  data: Record<string, unknown>[]
  narrative: Narrative | null
  isLoading: boolean
  sql?: string
}

type SortDir = "asc" | "desc" | null
interface SortState { col: string; dir: SortDir }

function DataTable({ data }: { data: Record<string, unknown>[] }) {
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<SortState>({ col: "", dir: null })
  const PAGE_SIZE = 25

  if (data.length === 0) return <p className="text-sm text-gray-400 text-center py-6">No data</p>

  const cols = Object.keys(data[0])

  function toggleSort(col: string) {
    setSort((s) =>
      s.col === col
        ? { col, dir: s.dir === "asc" ? "desc" : s.dir === "desc" ? null : "asc" }
        : { col, dir: "asc" }
    )
    setPage(0)
  }

  let rows = [...data]
  if (sort.dir && sort.col) {
    rows.sort((a, b) => {
      const av = a[sort.col]
      const bv = b[sort.col]
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av ?? "").localeCompare(String(bv ?? ""))
      return sort.dir === "asc" ? cmp : -cmp
    })
  }

  const pageData = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(rows.length / PAGE_SIZE)

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100">
              {cols.map((c) => (
                <th key={c} onClick={() => toggleSort(c)}
                  className="text-left px-2 py-2 font-semibold text-gray-500 cursor-pointer hover:text-gray-900 whitespace-nowrap">
                  {c} {sort.col === c ? (sort.dir === "asc" ? "↑" : sort.dir === "desc" ? "↓" : "") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, i) => (
              <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                {cols.map((c) => (
                  <td key={c} className="px-2 py-1.5 text-gray-700 whitespace-nowrap">{String(row[c] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="disabled:opacity-30">← Prev</button>
          <span>Page {page + 1} / {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)} className="disabled:opacity-30">Next →</button>
        </div>
      )}
    </div>
  )
}

function renderChart(config: ChartConfig, data: Record<string, unknown>[]) {
  const xKey = config.x_axis ?? (Object.keys(data[0] ?? {})[0] || "x")
  const yKey = Array.isArray(config.y_axis) ? config.y_axis[0] : config.y_axis ?? (Object.keys(data[0] ?? {})[1] || "y")

  switch (config.chart_type) {
    case "line":
      return (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey={yKey} stroke="#111827" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )
    case "bar":
      return (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey={yKey} fill="#111827" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )
    case "pie":
      return (
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={100} label>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )
    case "scatter":
      return (
        <ResponsiveContainer width="100%" height={260}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis dataKey={xKey} name={xKey} tick={{ fontSize: 11 }} />
            <YAxis dataKey={yKey} name={yKey} tick={{ fontSize: 11 }} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={data} fill="#111827" />
          </ScatterChart>
        </ResponsiveContainer>
      )
    default:
      return <DataTable data={data} />
  }
}

export default function ChartTile({ chartConfig, data, narrative, isLoading, sql }: Props) {
  const [showSql, setShowSql] = useState(false)
  const [copied, setCopied] = useState(false)

  function copySql() {
    if (sql) {
      navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-2xl p-4 animate-pulse">
        <div className="h-4 bg-gray-100 rounded w-1/2 mb-3" />
        <div className="h-48 bg-gray-100 rounded" />
      </div>
    )
  }

  if (!chartConfig && (!data || data.length === 0)) {
    return (
      <div className="bg-white border border-gray-200 rounded-2xl p-6 text-center text-gray-400 text-sm">
        No data to display
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-semibold text-sm text-gray-900">{chartConfig?.title ?? "Result"}</h3>
          {narrative?.headline && (
            <p className="text-xs text-gray-500 mt-0.5">{narrative.headline}</p>
          )}
        </div>
        <div className="flex gap-1">
          {sql && (
            <button onClick={copySql}
              className="text-xs border border-gray-200 rounded px-2 py-0.5 hover:bg-gray-50">
              {copied ? "Copied!" : "Copy SQL"}
            </button>
          )}
          {sql && (
            <button onClick={() => setShowSql((s) => !s)}
              className="text-xs border border-gray-200 rounded px-2 py-0.5 hover:bg-gray-50">
              SQL
            </button>
          )}
        </div>
      </div>

      {/* SQL preview */}
      {showSql && sql && (
        <pre className="text-xs bg-gray-50 rounded-lg p-3 mb-3 overflow-x-auto">{sql}</pre>
      )}

      {/* Chart */}
      {chartConfig && data.length > 0
        ? renderChart(chartConfig, data)
        : <DataTable data={data} />}

      {/* Narrative */}
      {narrative && (
        <div className="mt-3 border-t border-gray-100 pt-3 space-y-1">
          {narrative.supporting.map((s, i) => (
            <p key={i} className="text-xs text-gray-500">{s}</p>
          ))}
          {narrative.recommendation && (
            <span className="inline-block mt-1 text-xs bg-gray-900 text-white px-2 py-0.5 rounded-full">
              {narrative.recommendation}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
