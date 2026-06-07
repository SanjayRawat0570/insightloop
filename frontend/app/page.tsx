"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { isAuthenticated } from "../lib/api"

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    router.replace(isAuthenticated() ? "/chat" : "/login")
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
    </div>
  )
}
