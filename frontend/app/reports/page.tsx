"use client"

import { useEffect, useState } from "react"
import ReportScheduler from "../../components/ReportScheduler"
import AppShell, { PageHeader } from "../../components/AppShell"
import { deleteReport, getReports, runReport, type Report } from "../../lib/api"
import { PlusIcon, ReportIcon, BoltIcon, TrashIcon } from "../../components/icons"

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [showModal, setShowModal] = useState(false)
  const [toast, setToast] = useState("")

  async function loadReports() {
    getReports().then((r) => setReports(r.items)).catch(() => null)
  }

  useEffect(() => { loadReports() }, [])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(""), 3500)
  }

  async function handleRun(id: string) {
    showToast("Running report…")
    try {
      await runReport(id)
      showToast("Report triggered!")
      loadReports()
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Failed to run report")
    }
  }

  async function handleDelete(id: string) {
    await deleteReport(id).catch(() => null)
    loadReports()
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-6 py-10">
        <PageHeader
          title="Reports"
          subtitle="Schedule and manage automated PDF reports."
          action={
            <button onClick={() => setShowModal(true)} className="btn-primary">
              <PlusIcon className="h-4 w-4" /> New report
            </button>
          }
        />

        {reports.length === 0 ? (
          <div className="card flex flex-col items-center justify-center gap-3 py-24 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-500">
              <ReportIcon className="h-7 w-7" />
            </div>
            <p className="text-lg font-semibold text-slate-900">No reports yet</p>
            <p className="text-sm text-slate-500">Schedule your first automated report.</p>
            <button onClick={() => setShowModal(true)} className="btn-primary mt-2">
              <PlusIcon className="h-4 w-4" /> Create report
            </button>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-xs uppercase tracking-wider text-slate-400">
                  <th className="px-5 py-3 text-left font-semibold">Name</th>
                  <th className="px-5 py-3 text-left font-semibold">Schedule</th>
                  <th className="px-5 py-3 text-left font-semibold">Last run</th>
                  <th className="px-5 py-3 text-left font-semibold">Status</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id} className="border-b border-slate-50 transition last:border-0 hover:bg-slate-50/60">
                    <td className="px-5 py-3.5 font-medium text-slate-900">{r.name}</td>
                    <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{r.schedule_cron ?? "Manual"}</td>
                    <td className="px-5 py-3.5 text-slate-500">{r.last_run_at ? r.last_run_at.slice(0, 10) : "Never"}</td>
                    <td className="px-5 py-3.5">
                      <span className={`badge ${r.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${r.is_active ? "bg-emerald-500" : "bg-slate-400"}`} />
                        {r.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex justify-end gap-1.5">
                        {r.output_s3_url && (
                          <a href={r.output_s3_url} target="_blank" rel="noreferrer" className="btn-secondary btn-sm">
                            Download PDF
                          </a>
                        )}
                        <button onClick={() => handleRun(r.id)} className="btn-secondary btn-sm">
                          <BoltIcon className="h-3.5 w-3.5" /> Run now
                        </button>
                        <button onClick={() => handleDelete(r.id)} className="btn-danger btn-sm">
                          <TrashIcon className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {showModal && (
          <ReportScheduler
            onClose={() => setShowModal(false)}
            onCreated={() => { loadReports(); setShowModal(false); showToast("Report scheduled!") }}
          />
        )}

        {toast && (
          <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm text-white shadow-card animate-fade-in-up">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            {toast}
          </div>
        )}
      </div>
    </AppShell>
  )
}
