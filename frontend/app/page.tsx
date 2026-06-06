"use client"

import type { CSSProperties } from "react"
import { useEffect, useMemo, useState } from "react"
import AgentTrace from "../components/AgentTrace"

export default function Home() {
  const [clientId] = useState(() => crypto.randomUUID())
  const [health, setHealth] = useState<string>("checking")
  const [apiUrl, setApiUrl] = useState(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")

  useEffect(() => {
    let cancelled = false

    async function checkHealth() {
      try {
        const response = await fetch(`${apiUrl}/health`)
        const data = await response.json()
        if (!cancelled) {
          setHealth(data.status || "ok")
        }
      } catch {
        if (!cancelled) {
          setHealth("offline")
        }
      }
    }

    checkHealth()
    return () => {
      cancelled = true
    }
  }, [apiUrl])

  const statusTone = useMemo(() => {
    if (health === "ok") return "#166534"
    if (health === "offline") return "#991b1b"
    return "#7c2d12"
  }, [health])

  return (
    <main style={styles.page}>
      <section style={styles.hero}>
        <div style={styles.badge}>InsightLoop</div>
        <h1 style={styles.title}>Run the backend, watch the agent trace, and ship queries.</h1>
        <p style={styles.subtitle}>
          Frontend connects to the FastAPI backend health endpoint and websocket stream.
          Start both services locally, then use the trace below to watch live events.
        </p>

        <div style={styles.row}>
          <label style={styles.label}>
            Backend URL
            <input
              style={styles.input}
              value={apiUrl}
              onChange={(event) => setApiUrl(event.target.value)}
              placeholder="http://localhost:8000"
            />
          </label>
          <div style={{ ...styles.statusCard, borderColor: statusTone }}>
            <span style={{ ...styles.statusDot, background: statusTone }} />
            <span>Backend: {health}</span>
          </div>
        </div>
      </section>

      <section style={styles.grid}>
        <article style={styles.card}>
          <h2 style={styles.cardTitle}>Local setup</h2>
          <ol style={styles.list}>
            <li>Start MongoDB and the FastAPI backend.</li>
            <li>Start this Next.js app with `npm run dev`.</li>
            <li>Use the agent trace panel to monitor websocket events.</li>
          </ol>
        </article>

        <article style={styles.card}>
          <h2 style={styles.cardTitle}>Live trace</h2>
          <p style={styles.helper}>Client ID: {clientId}</p>
          <AgentTrace clientId={clientId} />
        </article>
      </section>
    </main>
  )
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "40px 20px",
    maxWidth: 1180,
    margin: "0 auto",
  },
  hero: {
    padding: "28px 28px 18px",
    borderRadius: 24,
    background: "rgba(255,255,255,0.72)",
    border: "1px solid rgba(17,24,39,0.08)",
    boxShadow: "0 18px 60px rgba(17,24,39,0.08)",
    marginBottom: 24,
    backdropFilter: "blur(10px)",
  },
  badge: {
    display: "inline-block",
    padding: "6px 12px",
    borderRadius: 999,
    background: "#111827",
    color: "#fff",
    fontSize: 12,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 18,
  },
  title: {
    margin: 0,
    fontSize: "clamp(2rem, 6vw, 4.5rem)",
    lineHeight: 1.05,
    maxWidth: 900,
  },
  subtitle: {
    maxWidth: 760,
    fontSize: 18,
    lineHeight: 1.6,
    color: "#444",
    marginTop: 16,
    marginBottom: 24,
  },
  row: {
    display: "flex",
    flexWrap: "wrap",
    gap: 16,
    alignItems: "end",
  },
  label: {
    display: "grid",
    gap: 8,
    minWidth: 280,
    fontWeight: 600,
  },
  input: {
    border: "1px solid rgba(17,24,39,0.15)",
    borderRadius: 14,
    padding: "12px 14px",
    background: "#fff",
    minWidth: 280,
  },
  statusCard: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    border: "1px solid",
    borderRadius: 999,
    padding: "10px 16px",
    background: "#fff",
    fontWeight: 600,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    display: "inline-block",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: 20,
  },
  card: {
    padding: 24,
    borderRadius: 22,
    background: "rgba(255,255,255,0.88)",
    border: "1px solid rgba(17,24,39,0.08)",
    boxShadow: "0 10px 30px rgba(17,24,39,0.06)",
  },
  cardTitle: {
    margin: 0,
    marginBottom: 14,
    fontSize: 22,
  },
  list: {
    margin: 0,
    paddingLeft: 20,
    lineHeight: 1.8,
    color: "#333",
  },
  helper: {
    marginTop: 0,
    marginBottom: 14,
    color: "#555",
    fontSize: 14,
  },
}
