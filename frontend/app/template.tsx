"use client"

/**
 * A template re-mounts on every navigation (unlike layout), so wrapping the
 * page in an entrance animation gives a smooth route transition app-wide.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-in">{children}</div>
}
