'use client'

import { useState } from 'react'
import ArchBotForm from '@/components/ArchBotForm'
import ResultPanel from '@/components/ResultPanel'
import Header from '@/components/Header'
import type { ArchitectureResponse } from '@/types/api'

export default function Home() {
  const [result, setResult] = useState<ArchitectureResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate(payload: unknown) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
      const res = await fetch(`${apiBase}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail ?? `HTTP ${res.status}`)
      }
      const data: ArchitectureResponse = await res.json()
      setResult(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <main className="flex-1 container mx-auto max-w-5xl px-4 py-8 space-y-8">
        <ArchBotForm onGenerate={handleGenerate} loading={loading} />

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30 p-4 text-red-700 dark:text-red-400 text-sm">
            <strong>Error:</strong> {error}
          </div>
        )}

        {result && <ResultPanel result={result} />}
      </main>

      <footer className="border-t border-gray-200 dark:border-gray-800 py-4 text-center text-xs text-gray-400 dark:text-gray-600">
        ArchBot — built with Amazon Bedrock + AWS CDK ·{' '}
        <a
          href="https://github.com/Konstantinos-Mavridis/aws-archbot"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-gray-600 dark:hover:text-gray-400"
        >
          View on GitHub
        </a>
      </footer>
    </div>
  )
}
