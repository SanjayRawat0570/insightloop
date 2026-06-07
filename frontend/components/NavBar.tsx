"use client"

import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { getUser, logout } from "../lib/api"

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
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
      <a href="/chat" className="font-bold text-sm tracking-tight">InsightLoop</a>

      <nav className="flex items-center gap-1 flex-1">
        {LINKS.map((l) => {
          const active = pathname === l.href
          return (
            <a
              key={l.href}
              href={l.href}
              className={`text-sm rounded-lg px-3 py-1.5 transition ${
                active ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {l.label}
            </a>
          )
        })}
      </nav>

      {email && <span className="text-xs text-gray-400 hidden sm:inline">{email}</span>}
      <button
        onClick={() => logout()}
        className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
      >
        Logout
      </button>
    </header>
  )
}
