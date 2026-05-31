import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ArchBot — AI-Powered AWS Architecture Advisor',
  description:
    'Describe your workload. Get a reference architecture, Well-Architected review, and Mermaid diagram — powered by Amazon Bedrock.',
  openGraph: {
    title: 'ArchBot',
    description: 'AI-Powered AWS Architecture Advisor',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const t = localStorage.getItem('theme') ||
                  (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
                document.documentElement.classList.toggle('dark', t === 'dark');
              } catch {}
            `,
          }}
        />
      </head>
      <body className="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100 font-sans antialiased">
        {children}
      </body>
    </html>
  )
}
