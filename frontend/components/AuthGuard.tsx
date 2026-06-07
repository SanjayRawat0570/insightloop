"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { isAuthenticated } from "../lib/api"

/**
 * Client-side route guard. Renders nothing until it has confirmed a token is
 * present; if none is found it redirects to /login. Wrap protected pages with
 * this so they never flash their content to logged-out visitors.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (isAuthenticated()) {
      setReady(true)
    } else {
      router.replace("/login")
    }
  }, [router])

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400 text-sm">
        Loading…
      </div>
    )
  }

  return <>{children}</>
}
