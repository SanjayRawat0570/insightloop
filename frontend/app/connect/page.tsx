"use client"

import { useEffect, useState } from "react"
import AppShell, { PageHeader } from "../../components/AppShell"
import { connectSource, deleteSource, getSchema, getSources, type DataSource } from "../../lib/api"
import { CloseIcon, PlusIcon, TrashIcon, DatabaseIcon } from "../../components/icons"

const SOURCE_TYPES = [
  { key: "postgres", label: "PostgreSQL", icon: "🐘" },
  { key: "mysql", label: "MySQL", icon: "🐬" },
  { key: "csv", label: "CSV Upload", icon: "📄" },
  { key: "api", label: "REST API", icon: "🔌" },
  { key: "sheets", label: "Google Sheets", icon: "📊" },
] as const

type SourceType = (typeof SOURCE_TYPES)[number]["key"]

interface FormState {
  name: string
  host: string
  port: string
  database: string
  user: string
  password: string
  ssl: boolean
  url: string
}

const EMPTY_FORM: FormState = { name: "", host: "", port: "", database: "", user: "", password: "", ssl: false, url: "" }

export default function ConnectPage() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [selected, setSelected] = useState<SourceType | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const [loading, setLoading] = useState(false)
  const [schemaData, setSchemaData] = useState<Record<string, unknown> | null>(null)
  const [schemaSourceId, setSchemaSourceId] = useState<string | null>(null)

  async function loadSources() {
    try {
      const res = await getSources()
      setSources(res.items)
    } catch {
      // ignore
    }
  }

  useEffect(() => { loadSources() }, [])

  function updateForm(patch: Partial<FormState>) {
    setForm((f) => ({ ...f, ...patch }))
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setSuccess("")
    setLoading(true)
    try {
      const cfg =
        selected === "postgres" || selected === "mysql"
          ? { host: form.host, port: Number(form.port) || undefined, database: form.database, user: form.user, password: form.password, ssl: form.ssl }
          : selected === "api"
          ? { url: form.url }
          : {}
      await connectSource({ name: form.name, type: selected!, connection_config: cfg })
      setSuccess("Source connected successfully!")
      setSelected(null)
      setForm(EMPTY_FORM)
      loadSources()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to connect")
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string) {
    await deleteSource(id).catch(() => null)
    loadSources()
  }

  async function handleBrowseSchema(id: string) {
    try {
      const schema = await getSchema(id)
      setSchemaData(schema)
      setSchemaSourceId(id)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Schema fetch failed")
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-6 py-10">
        <PageHeader title="Data Sources" subtitle="Connect a database or API, then ask questions about it." />

        {success && (
          <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 animate-fade-in">
            {success}
          </div>
        )}

        {/* Source type grid */}
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {SOURCE_TYPES.map((s) => {
            const active = selected === s.key
            return (
              <button
                key={s.key}
                onClick={() => { setSelected(s.key); setForm(EMPTY_FORM); setError(""); setSuccess("") }}
                className={`flex flex-col items-center gap-2 rounded-2xl border-2 p-4 transition-all ${
                  active
                    ? "border-brand-500 bg-brand-50 shadow-soft"
                    : "border-slate-200 bg-white hover:border-brand-300 hover:bg-slate-50"
                }`}
              >
                <span className="text-3xl">{s.icon}</span>
                <span className="text-xs font-semibold text-slate-700">{s.label}</span>
              </button>
            )
          })}
        </div>

        {/* Connection form */}
        {selected && (
          <form onSubmit={handleSave} className="card mb-10 space-y-4 p-6 animate-fade-in-up">
            <h2 className="text-lg font-semibold capitalize text-slate-900">{selected} connection</h2>

            <div>
              <label className="label">Connection name</label>
              <input required value={form.name} onChange={(e) => updateForm({ name: e.target.value })}
                className="input" placeholder="My production DB" />
            </div>

            {(selected === "postgres" || selected === "mysql") && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Host</label>
                    <input value={form.host} onChange={(e) => updateForm({ host: e.target.value })}
                      className="input" placeholder="localhost" />
                  </div>
                  <div>
                    <label className="label">Port</label>
                    <input value={form.port} onChange={(e) => updateForm({ port: e.target.value })}
                      className="input" placeholder={selected === "postgres" ? "5432" : "3306"} />
                  </div>
                </div>
                <div>
                  <label className="label">Database</label>
                  <input value={form.database} onChange={(e) => updateForm({ database: e.target.value })}
                    className="input" placeholder="mydb" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Username</label>
                    <input value={form.user} onChange={(e) => updateForm({ user: e.target.value })}
                      className="input" />
                  </div>
                  <div>
                    <label className="label">Password</label>
                    <input type="password" value={form.password} onChange={(e) => updateForm({ password: e.target.value })}
                      className="input" />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={form.ssl} onChange={(e) => updateForm({ ssl: e.target.checked })}
                    className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
                  Use SSL
                </label>
              </>
            )}

            {selected === "api" && (
              <div>
                <label className="label">API URL</label>
                <input value={form.url} onChange={(e) => updateForm({ url: e.target.value })}
                  className="input" placeholder="https://api.example.com/data" />
              </div>
            )}

            {(selected === "csv" || selected === "sheets") && (
              <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
                CSV and Sheets connections use the dev sample dataset in this build. Just give it a name and save.
              </p>
            )}

            {error && <p className="text-sm text-rose-600">{error}</p>}

            <div className="flex gap-3 pt-1">
              <button type="submit" disabled={loading} className="btn-primary">
                {loading ? "Saving…" : "Save connection"}
              </button>
              <button type="button" onClick={() => setSelected(null)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        )}

        {/* Existing sources */}
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Connected sources</h2>
        {sources.length === 0 ? (
          <div className="card flex flex-col items-center gap-3 p-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <DatabaseIcon className="h-6 w-6" />
            </div>
            <p className="text-sm text-slate-500">No sources connected yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sources.map((s) => (
              <div key={s.id} className="card flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                    <DatabaseIcon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium text-slate-900">{s.name}</p>
                    <span className="badge bg-slate-100 text-slate-500">{s.type}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleBrowseSchema(s.id)} className="btn-secondary btn-sm">Browse schema</button>
                  <button onClick={() => handleDelete(s.id)} className="btn-danger btn-sm">
                    <TrashIcon className="h-3.5 w-3.5" /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Schema modal */}
        {schemaData && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 animate-fade-in">
            <div className="card w-full max-w-lg max-h-[80vh] overflow-y-auto p-6 shadow-card animate-fade-in-up">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-900">Schema</h3>
                <button onClick={() => { setSchemaData(null); setSchemaSourceId(null) }}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
                  <CloseIcon className="h-5 w-5" />
                </button>
              </div>
              <pre className="overflow-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">{JSON.stringify(schemaData, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
