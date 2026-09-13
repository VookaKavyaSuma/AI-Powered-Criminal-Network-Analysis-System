import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Nexus/AI · Intelligence Operations",
  description: "AI-powered criminal network analysis and investigative intelligence command center.",
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>
}
