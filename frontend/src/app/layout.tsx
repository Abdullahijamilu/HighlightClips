import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Football Highlight Clipper',
  description: 'Automatically clip and grade the best football moments using AI.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
