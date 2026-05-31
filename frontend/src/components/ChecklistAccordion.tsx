'use client'

import type { WellArchitectedChecklist, ChecklistItem, RiskLevel } from '@/types/api'

const PILLAR_LABELS: Record<keyof WellArchitectedChecklist, string> = {
  operational_excellence: 'Operational Excellence',
  security: 'Security',
  reliability: 'Reliability',
  performance_efficiency: 'Performance Efficiency',
  cost_optimization: 'Cost Optimization',
  sustainability: 'Sustainability',
}

const RISK_COLORS: Record<RiskLevel, string> = {
  HIGH: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  MEDIUM: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  LOW: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  GOOD_PRACTICE: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
}

interface Props {
  checklist: WellArchitectedChecklist
}

export default function ChecklistAccordion({ checklist }: Props) {
  const pillars = Object.keys(checklist) as (keyof WellArchitectedChecklist)[]

  const totalItems = pillars.reduce((sum, p) => sum + checklist[p].length, 0)
  const highRisks = pillars.reduce(
    (sum, p) => sum + checklist[p].filter((i) => i.risk_level === 'HIGH').length,
    0
  )

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="flex flex-wrap gap-3">
        <Stat label="Total findings" value={String(totalItems)} />
        <Stat label="High risk" value={String(highRisks)} accent="red" />
        <Stat
          label="Good practices"
          value={String(
            pillars.reduce((s, p) => s + checklist[p].filter((i) => i.risk_level === 'GOOD_PRACTICE').length, 0)
          )}
          accent="green"
        />
      </div>

      {/* Pillars */}
      {pillars.map((pillar) => {
        const items = checklist[pillar]
        if (items.length === 0) return null
        const hasHigh = items.some((i) => i.risk_level === 'HIGH')
        return (
          <details key={pillar} open={hasHigh} className="group border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden">
            <summary className="flex items-center justify-between cursor-pointer px-4 py-3 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition-colors select-none">
              <div className="flex items-center gap-2">
                <svg
                  className="w-4 h-4 text-gray-400 transition-transform group-open:rotate-90"
                  viewBox="0 0 16 16"
                  fill="currentColor"
                >
                  <path d="M6 4l4 4-4 4"/>
                </svg>
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {PILLAR_LABELS[pillar]}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {hasHigh && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 font-medium">
                    HIGH
                  </span>
                )}
                <span className="text-xs text-gray-400 dark:text-gray-500">{items.length} items</span>
              </div>
            </summary>
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {items.map((item, i) => (
                <ChecklistRow key={i} item={item} />
              ))}
            </div>
          </details>
        )
      })}
    </div>
  )
}

function ChecklistRow({ item }: { item: ChecklistItem }) {
  return (
    <div className="px-4 py-3 space-y-1">
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 shrink-0 text-xs font-medium px-1.5 py-0.5 rounded ${RISK_COLORS[item.risk_level]}`}>
          {item.risk_level.replace('_', ' ')}
        </span>
        <p className="text-sm font-medium text-gray-900 dark:text-white">{item.question}</p>
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-400 pl-2 border-l-2 border-gray-200 dark:border-gray-700">
        <span className="font-medium">Finding:</span> {item.finding}
      </p>
      {item.improvement_suggestion && (
        <p className="text-xs text-gray-500 dark:text-gray-500 pl-2 border-l-2 border-brand-200 dark:border-brand-800">
          <span className="font-medium text-brand-600 dark:text-brand-400">Suggestion:</span>{' '}
          {item.improvement_suggestion}
        </p>
      )}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: 'red' | 'green' }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-gray-400 dark:text-gray-500">{label}</span>
      <span
        className={`text-lg font-semibold tabular-nums ${
          accent === 'red'
            ? 'text-red-600 dark:text-red-400'
            : accent === 'green'
            ? 'text-green-600 dark:text-green-400'
            : 'text-gray-900 dark:text-white'
        }`}
      >
        {value}
      </span>
    </div>
  )
}
