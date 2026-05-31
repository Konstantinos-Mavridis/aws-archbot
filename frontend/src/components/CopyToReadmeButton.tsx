'use client'

import { useState } from 'react'
import type { ArchitectureResponse } from '@/types/api'

interface Props {
  result: ArchitectureResponse
}

export default function CopyToReadmeButton({ result }: Props) {
  const [copied, setCopied] = useState(false)

  function buildMarkdown(): string {
    const serviceTable = result.service_recommendations
      .map((r) => `| ${r.category} | ${r.service} | ${r.reasoning} |`)
      .join('\n')

    return [
      '## Architecture Summary',
      '',
      result.architecture_summary,
      '',
      '## Recommended AWS Services',
      '',
      '| Category | Service | Reasoning |',
      '|---|---|---|',
      serviceTable,
      '',
      '## Architecture Diagram',
      '',
      '```mermaid',
      result.mermaid_diagram,
      '```',
      '',
    ].join('\n')
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(buildMarkdown())
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for browsers without clipboard API
      const textarea = document.createElement('textarea')
      textarea.value = buildMarkdown()
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-700
                 bg-white dark:bg-gray-800 px-3 py-1.5 text-sm font-medium
                 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-750
                 transition-colors duration-150 focus-visible:outline-none
                 focus-visible:ring-2 focus-visible:ring-teal-600"
      aria-label="Copy architecture summary and diagram as Markdown for README"
    >
      {copied ? (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" className="text-green-600" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span className="text-green-600">Copied!</span>
        </>
      ) : (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" aria-hidden="true">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          Copy to README
        </>
      )}
    </button>
  )
}
