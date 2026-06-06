"use client"

import { useState } from "react"
import { createReport } from "../lib/api"

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

  const selectedLabel = SCHEDULE_OPTIONS.find((o) => o.value === scheduleOption)?.label ?? scheduleOption

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-xl">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-lg font-semibold">Schedule Report</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium mb-1">Report name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Weekly revenue summary"
            />
          </div>

          {/* Schedule */}
          <div>
            <label className="block text-sm font-medium mb-1">Schedule</label>
            <div className="grid grid-cols-2 gap-2">
              {SCHEDULE_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setScheduleOption(o.value)}
                  className={`text-sm border rounded-lg px-3 py-2 text-left transition ${
                    scheduleOption === o.value ? "border-gray-900 bg-gray-50" : "border-gray-200 hover:border-gray-400"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
            {scheduleOption === "custom" && (
              <div className="mt-2">
                <input
                  value={customCron}
                  onChange={(e) => setCustomCron(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                  placeholder="0 9 * * 1"
                />
                <p className="text-xs text-gray-400 mt-1">Standard cron expression (minute hour day month weekday)</p>
              </div>
            )}
          </div>

          {/* Recipients */}
          <div>
            <label className="block text-sm font-medium mb-1">Email recipients</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={recipientInput}
                onChange={(e) => setRecipientInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRecipient() } }}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="user@company.com"
              />
              <button type="button" onClick={addRecipient}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm hover:bg-gray-50">
                Add
              </button>
            </div>
            {recipients.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {recipients.map((r) => (
                  <span key={r} className="inline-flex items-center gap-1 bg-gray-100 text-xs rounded-full px-2 py-1">
                    {r}
                    <button type="button" onClick={() => removeRecipient(r)} className="text-gray-400 hover:text-red-500">×</button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-gray-900 text-white rounded-lg py-2 text-sm font-semibold hover:bg-gray-700 disabled:opacity-50"
            >
              {loading ? "Saving…" : "Create report"}
            </button>
            <button type="button" onClick={onClose}
              className="flex-1 border border-gray-200 rounded-lg py-2 text-sm hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
