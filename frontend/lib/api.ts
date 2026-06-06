const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"

function getToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem("token")
}

function setToken(token: string) {
  localStorage.setItem("token", token)
}

function clearToken() {
  localStorage.removeItem("token")
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, { ...init, headers })

  if (res.status === 401) {
    clearToken()
    if (typeof window !== "undefined") window.location.href = "/login"
    throw new Error("Unauthorized")
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail ?? `Request failed: ${res.status}`)
  }

  return res.json() as Promise<T>
}

// ─── Auth ────────────────────────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string
  token_type: string
  user: { id: string; email: string; plan: string }
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const data = await apiRequest<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
  setToken(data.access_token)
  return data
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const data = await apiRequest<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
  setToken(data.access_token)
  return data
}

export function logout() {
  clearToken()
  window.location.href = "/login"
}

// ─── Sources ─────────────────────────────────────────────────────────────────
export interface DataSource {
  id: string
  name: string
  type: string
  is_active: boolean
  created_at: string
}

export async function getSources(): Promise<{ items: DataSource[] }> {
  return apiRequest("/api/sources")
}

export async function connectSource(payload: {
  name: string
  type: string
  connection_config: Record<string, unknown>
}): Promise<DataSource> {
  return apiRequest("/api/sources", { method: "POST", body: JSON.stringify(payload) })
}

export async function deleteSource(id: string): Promise<void> {
  return apiRequest(`/api/sources/${id}`, { method: "DELETE" })
}

export async function getSchema(sourceId: string): Promise<{
  dialect: string
  tables: Array<{ name: string; columns: Array<{ name: string; type: string; sample_values: unknown[] }> }>
}> {
  return apiRequest(`/api/sources/${sourceId}/schema`, { method: "POST" })
}

// ─── Query ───────────────────────────────────────────────────────────────────
export interface QueryResult {
  id: string
  natural_language: string
  generated_sql: string
  result_cache: Record<string, unknown>[] | null
  execution_ms: number | null
  created_at: string
  analysis?: Record<string, unknown>
  chart_config?: ChartConfig
  narrative?: Narrative
}

export async function submitQuery(payload: {
  question: string
  source_id: string
  client_id: string
  dialect?: string
}): Promise<{ query_id: string }> {
  return apiRequest("/api/query", { method: "POST", body: JSON.stringify(payload) })
}

export async function getQuery(queryId: string): Promise<QueryResult> {
  return apiRequest(`/api/query/${queryId}`)
}

export async function getQueryHistory(): Promise<{ items: QueryResult[] }> {
  return apiRequest("/api/query/history")
}

// ─── Dashboards ──────────────────────────────────────────────────────────────
export interface Dashboard {
  id: string
  name: string
  layout_json: Record<string, unknown>
  created_at: string
}

export async function getDashboards(): Promise<{ items: Dashboard[] }> {
  return apiRequest("/api/dashboards")
}

export async function saveDashboard(payload: { name: string; layout_json: Record<string, unknown>; id?: string }): Promise<Dashboard> {
  if (payload.id) {
    return apiRequest(`/api/dashboards/${payload.id}`, { method: "PUT", body: JSON.stringify(payload) })
  }
  return apiRequest("/api/dashboards", { method: "POST", body: JSON.stringify(payload) })
}

// ─── Reports ─────────────────────────────────────────────────────────────────
export interface Report {
  id: string
  name: string
  dashboard_id: string | null
  schedule_cron: string | null
  last_run_at: string | null
  output_s3_url: string | null
  recipients: string[]
  is_active: boolean
  created_at: string
}

export async function getReports(): Promise<{ items: Report[] }> {
  return apiRequest("/api/reports")
}

export async function createReport(payload: {
  name: string
  dashboard_id?: string
  schedule_cron?: string
  recipients?: string[]
}): Promise<Report> {
  return apiRequest("/api/reports", { method: "POST", body: JSON.stringify(payload) })
}

export async function runReport(reportId: string): Promise<{ status: string }> {
  return apiRequest(`/api/reports/${reportId}/run`, { method: "POST" })
}

export async function deleteReport(reportId: string): Promise<void> {
  return apiRequest(`/api/reports/${reportId}`, { method: "DELETE" })
}

// ─── Types ───────────────────────────────────────────────────────────────────
export interface ChartConfig {
  chart_type: "line" | "bar" | "pie" | "scatter" | "table"
  x_axis: string | null
  y_axis: string | string[] | null
  color_by: string | null
  title: string
  subtitle?: string
}

export interface Narrative {
  headline: string
  supporting: string[]
  recommendation: string
  tone: string
}

// ─── WebSocket ───────────────────────────────────────────────────────────────
export type AgentEvent =
  | { event: "node_start"; node: string; timestamp: string }
  | { event: "node_complete"; node: string; timestamp: string; payload: Record<string, unknown> }
  | { event: "node_error"; node: string; timestamp: string; payload: { error: string } }
  | { event: "node_warning"; node: string; timestamp: string; payload: Record<string, unknown> }
  | { event: "pipeline_complete"; node: string; timestamp: string; payload: { result: QueryResult; report: Record<string, unknown> } }
  | { event: "pipeline_error"; node: string; timestamp: string; payload: { error: string } }

export function createAgentSocket(clientId: string, onEvent: (e: AgentEvent) => void): WebSocket {
  const ws = new WebSocket(`${WS_URL}/ws/${clientId}`)
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as AgentEvent
      onEvent(data)
    } catch {
      // ignore malformed messages
    }
  }
  return ws
}
