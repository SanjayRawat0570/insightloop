"use client"

import { useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { getUser, isAuthenticated, logout } from "../lib/api"
import {
  BrandMark,
  ChatIcon,
  DatabaseIcon,
  GridIcon,
  ReportIcon,
  LogoutIcon,
} from "./icons"

const NAV = [
  { href: "/chat", label: "Ask", Icon: ChatIcon },
  { href: "/connect", label: "Sources", Icon: DatabaseIcon },
  { href: "/dashboard", label: "Boards", Icon: GridIcon },
  { href: "/reports", label: "Reports", Icon: ReportIcon },
]

interface Props {
  children: React.ReactNode
  /** When true the content area scrolls; set false for full-height panes (chat). */
  scroll?: boolean
}

/**
 * Authenticated app chrome: a dark icon rail on the left and the page content
 * on the right. Includes the client-side auth guard so pages only need to wrap
 * their content in <AppShell>.
 */
export default function AppShell({ children, scroll = true }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const [ready, setReady] = useState(false)
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    if (isAuthenticated()) {
      setReady(true)
      setEmail(getUser()?.email ?? null)
    } else {
      router.replace("/login")
    }
  }, [router])

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      </div>
    )
  }

  const initial = (email?.[0] ?? "U").toUpperCase()

  return (
    <div className="flex h-screen overflow-hidden app-backdrop">
      {/* Icon rail */}
      <aside className="relative w-[84px] shrink-0 flex flex-col items-center gap-1 bg-gradient-to-b from-graphite-950 via-graphite-900 to-graphite-950 py-4 text-graphite-300 shadow-xl">
        {/* faint glow at the top of the rail */}
        <div className="pointer-events-none absolute -top-10 left-1/2 h-32 w-32 -translate-x-1/2 rounded-full bg-brand-500/20 blur-2xl" />

        <a href="/chat" className="relative mb-3 transition-transform duration-200 hover:scale-110 active:scale-95" title="InsightLoop">
          <BrandMark className="h-11 w-11" />
        </a>

        <nav className="relative flex flex-1 flex-col items-center gap-1.5 w-full px-2">
          {NAV.map(({ href, label, Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/")
            return (
              <a
                key={href}
                href={href}
                title={label}
                className={`group relative flex w-full flex-col items-center gap-1 rounded-xl py-2.5 transition-all duration-200 ${
                  active
                    ? "bg-white/10 text-white shadow-inner"
                    : "hover:bg-white/5 hover:text-slate-100"
                }`}
              >
                <span
                  className={`absolute left-0 top-1/2 -translate-y-1/2 w-1 rounded-r-full bg-brand-gradient transition-all duration-300 ${
                    active ? "h-7 opacity-100" : "h-0 opacity-0"
                  }`}
                />
                <Icon className="h-[22px] w-[22px] transition-transform duration-200 group-hover:scale-110 group-active:scale-95" />
                <span className="text-[10px] font-medium tracking-wide">{label}</span>
              </a>
            )
          })}
        </nav>

        <div className="relative flex flex-col items-center gap-3 w-full px-2">
          <div
            title={email ?? "Account"}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-gradient text-sm font-semibold text-white shadow-glow ring-2 ring-white/10 transition-transform duration-200 hover:scale-110"
          >
            {initial}
          </div>
          <button
            onClick={() => logout()}
            title="Log out"
            className="group flex w-full flex-col items-center gap-1 rounded-xl py-2 text-slate-400 transition-all duration-200 hover:bg-white/5 hover:text-rose-300"
          >
            <LogoutIcon className="h-[22px] w-[22px] transition-transform duration-200 group-hover:scale-110 group-hover:-translate-x-0.5" />
            <span className="text-[10px] font-medium">Logout</span>
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className={`flex-1 min-w-0 ${scroll ? "overflow-y-auto" : "overflow-hidden"}`}>
        {children}
      </main>
    </div>
  )
}

/** Consistent page header used by scrollable pages. */
export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: React.ReactNode
  subtitle?: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-8 animate-fade-in-up">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="text-slate-500 mt-1.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
