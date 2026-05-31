'use client'

import { useState } from 'react'
import type { ArchitectureResponse } from '@/types/api'
import MermaidDiagram from './MermaidDiagram'
import ChecklistAccordion from './ChecklistAccordion'

interface Props {
  result: ArchitectureResponse
}

const TABS = ['Summary', 'Diagram', 'Checklist'] as const
type Tab = typeof TABS[number]

export default function ResultPanel({ result }: Props) {
  const [tab, setTab] = useState<Tab>('Summary')
  const [copied, setCopied] = useState(false)

  function copyToReadme() {
    const block = [
      '## Architecture Summary',
      '',
      result.architecture_summary,
      '',
      '```mermaid',
      result.mermaid_diagram,
      '```',
    ].join('\n')
    navigator.clipboard.writeText(block).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
      {/* Tab bar */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 px-4">
        <div className="flex">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <button
          onClick={copyToReadme}
          className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors py-1.5 px-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
          title="Copy summary + Mermaid block for pasting into a README"
        >
          {copied ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2"/>
              <rect x="8" y="2" width="8" height="4" rx="1"/>
            </svg>
          )}
          {copied ? 'Copied!' : 'Copy to README'}
        </button>
      </div>

      {/* Tab content */}
      <div className="p-5 tab-content" key={tab}>
        {tab === 'Summary' && (
          <SummaryTab result={result} />
        )}
        {tab === 'Diagram' && (
          <MermaidDiagram diagram={result.mermaid_diagram} />
        )}
        {tab === 'Checklist' && (
          <ChecklistAccordion checklist={result.well_architected_checklist} />
        )}
      </div>
    </div>
  )
}

function SummaryTab({ result }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-2">Architecture summary</h2>
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
          {result.architecture_summary}
        </p>
      </div>

      <div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3">Service recommendations</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {result.service_recommendations.map((rec, i) => (
            <div
              key={i}
              className="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 p-3"
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 inline-block text-xs font-medium px-1.5 py-0.5 rounded bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300">
                  {rec.category}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{rec.service}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{rec.reasoning}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {result.cost_tiers.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3">Cost tiers</h2>
          <div className="flex flex-wrap gap-3">
            {result.cost_tiers.map((ct) => (
              <div
                key={ct.tier}
                className="flex-1 min-w-[140px] rounded-lg border border-gray-200 dark:border-gray-700 p-3"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">{ct.tier}</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white mt-0.5">{ct.monthly_estimate_hint}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{ct.assumptions}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
