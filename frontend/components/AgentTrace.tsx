"use client"
import React, { useEffect, useState } from "react"

type Event = { event: string; node?: string; timestamp?: string; payload?: any }

export default function AgentTrace({ clientId }: { clientId: string }) {
  const [events, setEvents] = useState<Event[]>([])

  useEffect(() => {
    if (!clientId) return
    const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000") + "/ws/" + clientId
    const ws = new WebSocket(wsUrl)
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        setEvents((s) => [data, ...s].slice(0, 20))
      } catch (e) {
        // ignore
      }
    }
    return () => ws.close()
  }, [clientId])

  return (
    <div className="p-4 bg-white shadow rounded">
      <h3 className="font-semibold mb-2">Agent Trace</h3>
      <ul className="space-y-2">
        {events.map((e, i) => (
          <li key={i} className="text-sm">
            <strong>{e.event}</strong>
            {e.node ? ` — ${e.node}` : ""}
            {e.payload ? `: ${JSON.stringify(e.payload)}` : ""}
          </li>
        ))}
        {events.length === 0 && <li className="text-sm text-gray-500">No events yet</li>}
      </ul>
    </div>
  )
}
