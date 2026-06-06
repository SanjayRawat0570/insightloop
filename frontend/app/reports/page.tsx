"use client"

import { useEffect, useState } from "react"
import ReportScheduler from "../../components/ReportScheduler"
import { deleteReport, getReports, runReport, type Report } from "../../lib/api"

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
    <div className="max-w-5xl mx-auto py-10 px-4">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="text-gray-500 mt-1">Schedule and manage automated PDF reports.</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-gray-900 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-gray-700"
        >
          + New report
        </button>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-24 text-gray-400">
          <p className="text-lg font-medium mb-2">No reports yet</p>
          <button onClick={() => setShowModal(true)} className="text-sm text-blue-600 hover:underline">
            Create your first report
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-500 text-xs">
                <th className="text-left px-4 py-3 font-semibold">Name</th>
                <th className="text-left px-4 py-3 font-semibold">Schedule</th>
                <th className="text-left px-4 py-3 font-semibold">Last run</th>
                <th className="text-left px-4 py-3 font-semibold">Status</th>
                <th className="text-right px-4 py-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{r.name}</td>
                  <td className="px-4 py-3 text-gray-500">{r.schedule_cron ?? "Manual"}</td>
                  <td className="px-4 py-3 text-gray-500">{r.last_run_at ? r.last_run_at.slice(0, 10) : "Never"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${r.is_active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {r.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    {r.output_s3_url && (
                      <a href={r.output_s3_url} target="_blank" rel="noreferrer"
                        className="text-xs border border-gray-200 rounded px-2 py-1 hover:bg-gray-50">
                        Download PDF
                      </a>
                    )}
                    <button onClick={() => handleRun(r.id)}
                      className="text-xs border border-gray-200 rounded px-2 py-1 hover:bg-gray-50">
                      Run now
                    </button>
                    <button onClick={() => handleDelete(r.id)}
                      className="text-xs border border-red-200 text-red-600 rounded px-2 py-1 hover:bg-red-50">
                      Delete
                    </button>
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
        <div className="fixed bottom-6 right-6 bg-gray-900 text-white text-sm rounded-xl px-4 py-3 shadow-lg z-50">
          {toast}
        </div>
      )}
    </div>
  )
}
