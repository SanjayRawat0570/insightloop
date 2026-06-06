"use client"

import { useEffect, useState } from "react"
import { connectSource, deleteSource, getSchema, getSources, type DataSource } from "../../lib/api"

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
    <div className="max-w-4xl mx-auto py-10 px-4">
      <h1 className="text-3xl font-bold mb-2">Connect a Data Source</h1>
      <p className="text-gray-500 mb-8">Choose a source type, fill in credentials, and save.</p>

      {/* Source type grid */}
      <div className="grid grid-cols-3 gap-4 mb-8 sm:grid-cols-5">
        {SOURCE_TYPES.map((s) => (
          <button
            key={s.key}
            onClick={() => { setSelected(s.key); setForm(EMPTY_FORM); setError(""); setSuccess("") }}
            className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition ${
              selected === s.key ? "border-gray-900 bg-gray-50" : "border-gray-200 hover:border-gray-400"
            }`}
          >
            <span className="text-2xl">{s.icon}</span>
            <span className="text-xs font-semibold">{s.label}</span>
          </button>
        ))}
      </div>

      {/* Connection form */}
      {selected && (
        <form onSubmit={handleSave} className="bg-white rounded-2xl border border-gray-200 p-6 mb-8 space-y-4">
          <h2 className="font-semibold text-lg capitalize">{selected} Connection</h2>

          <div>
            <label className="block text-sm font-medium mb-1">Connection name</label>
            <input required value={form.name} onChange={(e) => updateForm({ name: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="My production DB" />
          </div>

          {(selected === "postgres" || selected === "mysql") && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Host</label>
                  <input value={form.host} onChange={(e) => updateForm({ host: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="localhost" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Port</label>
                  <input value={form.port} onChange={(e) => updateForm({ port: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" placeholder={selected === "postgres" ? "5432" : "3306"} />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Database</label>
                <input value={form.database} onChange={(e) => updateForm({ database: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="mydb" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Username</label>
                  <input value={form.user} onChange={(e) => updateForm({ user: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Password</label>
                  <input type="password" value={form.password} onChange={(e) => updateForm({ password: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.ssl} onChange={(e) => updateForm({ ssl: e.target.checked })} />
                Use SSL
              </label>
            </>
          )}

          {selected === "api" && (
            <div>
              <label className="block text-sm font-medium mb-1">API URL</label>
              <input value={form.url} onChange={(e) => updateForm({ url: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="https://api.example.com/data" />
            </div>
          )}

          {(selected === "csv" || selected === "sheets") && (
            <p className="text-sm text-gray-500">CSV and Sheets connections require additional setup. Contact support.</p>
          )}

          {error && <p className="text-red-600 text-sm">{error}</p>}
          {success && <p className="text-green-600 text-sm">{success}</p>}

          <div className="flex gap-3">
            <button type="submit" disabled={loading}
              className="bg-gray-900 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-gray-700 disabled:opacity-50">
              {loading ? "Saving…" : "Save connection"}
            </button>
            <button type="button" onClick={() => setSelected(null)}
              className="border border-gray-200 rounded-lg px-4 py-2 text-sm">Cancel</button>
          </div>
        </form>
      )}

      {/* Existing sources */}
      <h2 className="font-semibold text-lg mb-4">Connected sources</h2>
      {sources.length === 0 ? (
        <p className="text-gray-400 text-sm">No sources connected yet.</p>
      ) : (
        <div className="space-y-3">
          {sources.map((s) => (
            <div key={s.id} className="flex items-center justify-between bg-white border border-gray-200 rounded-xl px-4 py-3">
              <div>
                <span className="font-medium">{s.name}</span>
                <span className="ml-2 text-xs bg-gray-100 rounded px-2 py-0.5">{s.type}</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleBrowseSchema(s.id)}
                  className="text-xs border border-gray-200 rounded px-2 py-1 hover:bg-gray-50">Browse schema</button>
                <button onClick={() => handleDelete(s.id)}
                  className="text-xs border border-red-200 text-red-600 rounded px-2 py-1 hover:bg-red-50">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Schema modal */}
      {schemaData && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-lg">Schema</h3>
              <button onClick={() => { setSchemaData(null); setSchemaSourceId(null) }}
                className="text-gray-400 hover:text-gray-700">✕</button>
            </div>
            <pre className="text-xs bg-gray-50 rounded-lg p-4 overflow-auto">{JSON.stringify(schemaData, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
