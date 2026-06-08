"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login, register } from "../../../lib/api"
import { BrandMark, SparkleIcon, BoltIcon, ChatIcon, ReportIcon } from "../../../components/icons"

const HIGHLIGHTS = [
  { Icon: ChatIcon, title: "Ask in plain English", desc: "No SQL required — just type your question." },
  { Icon: BoltIcon, title: "Agentic pipeline", desc: "Agents write SQL, analyze, chart & narrate." },
  { Icon: ReportIcon, title: "Auto reports", desc: "Schedule polished PDF insights to your inbox." },
]

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      if (mode === "login") {
        await login(email, password)
      } else {
        await register(email, password)
      }
      router.push("/chat")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Brand / showcase panel */}
      <div className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-gradient-to-br from-slate-900 via-brand-950 to-brand-800 p-12 text-white">
        {/* Decorative glows (gently drifting) */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-96 w-96 rounded-full bg-violet-500/30 blur-3xl animate-float" />
        <div className="pointer-events-none absolute bottom-0 -left-24 h-96 w-96 rounded-full bg-fuchsia-500/20 blur-3xl animate-pulse-soft" />
        {/* Faint grid texture */}
        <div className="pointer-events-none absolute inset-0 bg-grid-slate bg-grid opacity-[0.04]" />

        <div className="relative flex items-center gap-3">
          <BrandMark className="h-11 w-11" />
          <span className="text-xl font-bold tracking-tight">InsightLoop</span>
        </div>

        <div className="relative max-w-md">
          <span className="badge bg-white/10 text-brand-100 mb-5">
            <SparkleIcon className="h-3.5 w-3.5" /> AI-native BI
          </span>
          <h2 className="text-4xl font-bold leading-tight tracking-tight">
            Turn questions into <span className="text-gradient bg-gradient-to-r from-violet-300 to-fuchsia-300">decisions</span>.
          </h2>
          <p className="mt-4 text-slate-300 leading-relaxed">
            Connect your data, ask in plain English, and let a team of AI agents
            generate SQL, surface insights, and build reports — in seconds.
          </p>

          <div className="mt-9 space-y-2">
            {HIGHLIGHTS.map(({ Icon, title, desc }, i) => (
              <div
                key={title}
                style={{ animationDelay: `${150 + i * 90}ms` }}
                className="group flex items-start gap-3.5 rounded-xl p-2 -mx-2 transition-all duration-200 animate-fade-in-up hover:bg-white/5"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/10 transition-all duration-200 group-hover:scale-110 group-hover:bg-white/15">
                  <Icon className="h-5 w-5 text-violet-200" />
                </div>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="text-sm text-slate-400">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-slate-400">
          © {new Date().getFullYear()} InsightLoop. Built for analysts who move fast.
        </p>
      </div>

      {/* Auth form panel */}
      <div className="flex items-center justify-center app-backdrop p-6 sm:p-10">
        <div className="w-full max-w-md animate-fade-in-up">
          {/* Mobile brand */}
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <BrandMark className="h-10 w-10" />
            <span className="text-lg font-bold">InsightLoop</span>
          </div>

          <div className="card p-8 shadow-card">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </h1>
            <p className="mt-1.5 text-sm text-slate-500">
              {mode === "login"
                ? "Sign in to continue to your workspace."
                : "Start exploring your data in minutes."}
            </p>

            <form onSubmit={handleSubmit} className="mt-7 space-y-5">
              <div>
                <label className="label">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input"
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <label className="label">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input"
                  placeholder="••••••••"
                />
              </div>

              {error && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
                  {error}
                </div>
              )}

              <button type="submit" disabled={loading} className="btn-primary w-full py-2.5">
                {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-500">
              {mode === "login" ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => { setMode(mode === "login" ? "register" : "login"); setError("") }}
                className="font-semibold text-brand-600 hover:text-brand-700 hover:underline"
              >
                {mode === "login" ? "Create one" : "Sign in"}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
