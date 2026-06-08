"use client"

import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { getUser, logout } from "../lib/api"
import { BrandMark } from "./icons"

const LINKS = [
  { href: "/chat", label: "Chat" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/connect", label: "Sources" },
  { href: "/reports", label: "Reports" },
]

/**
 * Shared top navigation with brand, primary links, the signed-in user's email
 * and a logout button. Used by pages that don't have their own chrome.
 */
export default function NavBar() {
  const pathname = usePathname()
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    setEmail(getUser()?.email ?? null)
  }, [])

  return (
    <header className="sticky top-0 z-40 glass border-b px-6 py-3 flex items-center gap-6">
      <a href="/chat" className="flex items-center gap-2 font-bold text-sm tracking-tight text-slate-900 transition-transform hover:scale-[1.02]">
        <BrandMark className="h-7 w-7" />
        InsightLoop
      </a>

      <nav className="flex items-center gap-1 flex-1">
        {LINKS.map((l) => {
          const active = pathname === l.href
          return (
            <a
              key={l.href}
              href={l.href}
              className={`text-sm rounded-lg px-3 py-1.5 font-medium transition-all duration-150 ${
                active
                  ? "bg-brand-gradient text-white shadow-glow"
                  : "text-slate-600 hover:bg-slate-100 hover:-translate-y-0.5"
              }`}
            >
              {l.label}
            </a>
          )
        })}
      </nav>

      {email && <span className="text-xs text-slate-400 hidden sm:inline">{email}</span>}
      <button
        onClick={() => logout()}
        className="btn-secondary btn-sm"
      >
        Logout
      </button>
    </header>
  )
}
