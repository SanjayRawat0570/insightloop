"use client"

import { useState } from "react"
import cronstrue from "cronstrue"
import { createReport } from "../lib/api"
import { CloseIcon, PlusIcon } from "./icons"

interface Props {
  onClose: () => void
  onCreated: () => void
}

const SCHEDULE_OPTIONS = [
  { label: "Daily at 9am", value: "0 9 * * *" },
  { label: "Weekly (Mon 9am)", value: "0 9 * * 1" },
  { label: "Monthly (1st, 9am)", value: "0 9 1 * *" },
  { label: "Custom cron", value: "custom" },
] as const

function describeCron(expr: string): string {
  if (!expr.trim()) return ""
  try {
    return cronstrue.toString(expr, { use24HourTimeFormat: false })
  } catch {
    return "Invalid cron expression"
  }
}

export default function ReportScheduler({ onClose, onCreated }: Props) {
  const [name, setName] = useState("")
  const [scheduleOption, setScheduleOption] = useState<string>("0 9 * * 1")
  const [customCron, setCustomCron] = useState("")
  const [recipientInput, setRecipientInput] = useState("")
  const [recipients, setRecipients] = useState<string[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  function addRecipient() {
    const email = recipientInput.trim()
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return
    if (!recipients.includes(email)) setRecipients((r) => [...r, email])
    setRecipientInput("")
  }

  function removeRecipient(email: string) {
    setRecipients((r) => r.filter((e) => e !== email))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    if (!name.trim()) { setError("Report name is required"); return }

    const cron = scheduleOption === "custom" ? customCron.trim() : scheduleOption
    setLoading(true)
    try {
      await createReport({ name: name.trim(), schedule_cron: cron || undefined, recipients })
      onCreated()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create report")
    } finally {
      setLoading(false)
    }
  }

  const activeCron = scheduleOption === "custom" ? customCron : scheduleOption
  const preview = describeCron(activeCron)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 animate-fade-in">
      <div className="card w-full max-w-md p-6 shadow-card animate-fade-in-up">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Schedule report</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div>
            <label className="label">Report name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              placeholder="Weekly revenue summary"
            />
          </div>

          {/* Schedule */}
          <div>
            <label className="label">Schedule</label>
            <div className="grid grid-cols-2 gap-2">
              {SCHEDULE_OPTIONS.map((o) => {
                const active = scheduleOption === o.value
                return (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => setScheduleOption(o.value)}
                    className={`rounded-xl border-2 px-3 py-2 text-left text-sm transition ${
                      active ? "border-brand-500 bg-brand-50 text-brand-800" : "border-slate-200 text-slate-600 hover:border-brand-300"
                    }`}
                  >
                    {o.label}
                  </button>
                )
              })}
            </div>
            {scheduleOption === "custom" && (
              <input
                value={customCron}
                onChange={(e) => setCustomCron(e.target.value)}
                className="input mt-2 font-mono"
                placeholder="0 9 * * 1"
              />
            )}
            {preview && (
              <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
                🕑 {preview}
              </p>
            )}
          </div>

          {/* Recipients */}
          <div>
            <label className="label">Email recipients</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={recipientInput}
                onChange={(e) => setRecipientInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRecipient() } }}
                className="input"
                placeholder="user@company.com"
              />
              <button type="button" onClick={addRecipient} className="btn-secondary shrink-0">
                <PlusIcon className="h-4 w-4" /> Add
              </button>
            </div>
            {recipients.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {recipients.map((r) => (
                  <span key={r} className="badge bg-brand-50 text-brand-700">
                    {r}
                    <button type="button" onClick={() => removeRecipient(r)} className="text-brand-400 hover:text-rose-500">×</button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {error && <p className="text-sm text-rose-600">{error}</p>}

          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={loading} className="btn-primary flex-1">
              {loading ? "Saving…" : "Create report"}
            </button>
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}
