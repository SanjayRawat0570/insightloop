"use client"

import { useState } from "react"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts"
import type { ChartConfig, Narrative } from "../lib/api"
import { CopyIcon, CodeIcon, CheckIcon, BoltIcon } from "./icons"

// Vibrant, accessible palette anchored on the brand hue.
const COLORS = ["#6366f1", "#8b5cf6", "#d946ef", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#3b82f6"]
const PRIMARY = "#6366f1"

interface Props {
  chartConfig: ChartConfig | null
  data: Record<string, unknown>[]
  narrative: Narrative | null
  isLoading: boolean
  sql?: string
}

type SortDir = "asc" | "desc" | null
interface SortState { col: string; dir: SortDir }

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #e2e8f0",
  boxShadow: "0 8px 24px -8px rgb(15 23 42 / 0.15)",
  fontSize: 12,
}

function DataTable({ data }: { data: Record<string, unknown>[] }) {
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<SortState>({ col: "", dir: null })
  const PAGE_SIZE = 25

  if (data.length === 0) return <p className="py-8 text-center text-sm text-slate-400">No data</p>

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
      <div className="overflow-x-auto rounded-xl border border-slate-100">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-50">
              {cols.map((c) => (
                <th key={c} onClick={() => toggleSort(c)}
                  className="cursor-pointer whitespace-nowrap px-3 py-2.5 text-left font-semibold text-slate-500 transition hover:text-brand-600">
                  {c} {sort.col === c ? (sort.dir === "asc" ? "↑" : sort.dir === "desc" ? "↓" : "") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, i) => (
              <tr key={i} className="border-t border-slate-50 transition hover:bg-brand-50/40">
                {cols.map((c) => (
                  <td key={c} className="whitespace-nowrap px-3 py-2 text-slate-700">{String(row[c] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="btn-secondary btn-sm disabled:opacity-30">← Prev</button>
          <span>Page {page + 1} of {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)} className="btn-secondary btn-sm disabled:opacity-30">Next →</button>
        </div>
      )}
    </div>
  )
}

function renderChart(config: ChartConfig, data: Record<string, unknown>[]) {
  const xKey = config.x_axis ?? (Object.keys(data[0] ?? {})[0] || "x")
  const yKey = Array.isArray(config.y_axis) ? config.y_axis[0] : config.y_axis ?? (Object.keys(data[0] ?? {})[1] || "y")
  const axisTick = { fontSize: 11, fill: "#94a3b8" }

  switch (config.chart_type) {
    case "line":
      return (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="lineStroke" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="100%" stopColor="#d946ef" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey={xKey} tick={axisTick} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
            <YAxis tick={axisTick} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Line type="monotone" dataKey={yKey} stroke="url(#lineStroke)" strokeWidth={3} dot={{ r: 3, fill: PRIMARY }} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      )
    case "bar":
      return (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="barFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#6366f1" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey={xKey} tick={axisTick} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
            <YAxis tick={axisTick} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(99,102,241,0.06)" }} />
            <Bar dataKey={yKey} fill="url(#barFill)" radius={[6, 6, 0, 0]} maxBarSize={56} />
          </BarChart>
        </ResponsiveContainer>
      )
    case "pie":
      return (
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" innerRadius={55} outerRadius={100} paddingAngle={2} label>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="#fff" strokeWidth={2} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      )
    case "scatter":
      return (
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey={xKey} name={xKey} tick={axisTick} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
            <YAxis dataKey={yKey} name={yKey} tick={axisTick} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={data} fill={PRIMARY} />
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
      <div className="card p-5">
        <div className="mb-3 h-4 w-1/2 skeleton" />
        <div className="mb-4 h-3 w-1/3 skeleton" />
        <div className="h-56 skeleton rounded-xl" />
      </div>
    )
  }

  if (!chartConfig && (!data || data.length === 0)) {
    return (
      <div className="card p-8 text-center text-sm text-slate-400">
        No data to display
      </div>
    )
  }

  return (
    <div className="card-interactive group animate-fade-in-up overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-slate-900">{chartConfig?.title ?? "Result"}</h3>
          {narrative?.headline && (
            <p className="mt-0.5 truncate text-sm text-slate-500">{narrative.headline}</p>
          )}
        </div>
        {sql && (
          <div className="flex shrink-0 gap-1.5">
            <button onClick={copySql} className="btn-secondary btn-sm">
              {copied ? <CheckIcon className="h-3.5 w-3.5 text-emerald-600" /> : <CopyIcon className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "SQL"}
            </button>
            <button onClick={() => setShowSql((s) => !s)} className={`btn-sm ${showSql ? "btn-primary" : "btn-secondary"}`}>
              <CodeIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="p-5">
        {/* SQL preview */}
        {showSql && sql && (
          <pre className="mb-4 overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
            <code>{sql}</code>
          </pre>
        )}

        {/* Chart */}
        {chartConfig && data.length > 0 ? renderChart(chartConfig, data) : <DataTable data={data} />}

        {/* Narrative */}
        {narrative && (
          <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
            {narrative.supporting?.map((s, i) => (
              <p key={i} className="text-sm leading-relaxed text-slate-600">{s}</p>
            ))}
            {narrative.recommendation && (
              <div className="mt-2 flex items-start gap-2 rounded-xl bg-brand-gradient-soft p-3 text-sm text-brand-900 ring-1 ring-brand-100">
                <BoltIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                <span><span className="font-semibold">Recommendation:</span> {narrative.recommendation}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
