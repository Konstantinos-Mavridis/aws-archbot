'use client'

import { useState } from 'react'
import type { ArchitectureRequest, Lens } from '@/types/api'

const HELPER_CHIPS = [
  'FSI trading platform',
  'Healthcare clinical data',
  'E-commerce, high traffic',
  'IoT data ingestion',
  'ML training pipeline',
  'Multi-tenant SaaS',
]

const LENS_OPTIONS: { value: Lens; label: string; description: string }[] = [
  { value: 'general', label: 'General', description: 'AWS Well-Architected Framework' },
  { value: 'fsi', label: 'Financial Services', description: 'FSI Lens — PCI-DSS, SOX, data residency' },
  { value: 'healthcare', label: 'Healthcare', description: 'Healthcare Lens — HIPAA, PHI protection' },
]

interface Props {
  onGenerate: (payload: ArchitectureRequest) => void
  loading: boolean
}

export default function ArchBotForm({ onGenerate, loading }: Props) {
  const [description, setDescription] = useState('')
  const [lens, setLens] = useState<Lens>('general')
  const [sla, setSla] = useState('')
  const [regions, setRegions] = useState('')
  const [rto, setRto] = useState('')
  const [rpo, setRpo] = useState('')
  const [compliance, setCompliance] = useState('')

  function appendChip(chip: string) {
    setDescription((prev) => (prev ? `${prev.trimEnd()}, ${chip}` : chip))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!description.trim()) return
    const payload: ArchitectureRequest = {
      workload_description: description.trim(),
      lens,
      non_functionals: {
        ...(sla ? { sla_percent: parseFloat(sla) } : {}),
        ...(regions ? { regions: parseInt(regions) } : {}),
        ...(rto ? { rto_minutes: parseInt(rto) } : {}),
        ...(rpo ? { rpo_minutes: parseInt(rpo) } : {}),
        compliance_flags: compliance
          ? compliance.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
      },
    }
    onGenerate(payload)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Workload description
          <span className="ml-1 text-gray-400 dark:text-gray-500 font-normal">— describe your system in plain English</span>
        </label>
        <textarea
          id="description"
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. Regulated FSI trade finance platform, CQRS event sourcing, multi-region active-active, 99.99% SLA, PCI-DSS compliant"
          required
          minLength={10}
          maxLength={2000}
          className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2.5 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent resize-vertical transition-colors"
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {HELPER_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => appendChip(chip)}
              className="text-xs px-2.5 py-1 rounded-full border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
            >
              + {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Lens toggle */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Architecture lens</label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {LENS_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`relative flex flex-col gap-0.5 cursor-pointer rounded-lg border p-3 transition-colors ${
                lens === opt.value
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <input
                type="radio"
                name="lens"
                value={opt.value}
                checked={lens === opt.value}
                onChange={() => setLens(opt.value)}
                className="sr-only"
              />
              <span className="text-sm font-medium text-gray-900 dark:text-white">{opt.label}</span>
              <span className="text-xs text-gray-500 dark:text-gray-400">{opt.description}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Non-functional requirements */}
      <details className="group">
        <summary className="cursor-pointer select-none flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors">
          <svg className="w-4 h-4 transition-transform group-open:rotate-90" viewBox="0 0 16 16" fill="currentColor">
            <path d="M6 4l4 4-4 4"/>
          </svg>
          Non-functional requirements
          <span className="font-normal text-gray-400 dark:text-gray-500">(optional)</span>
        </summary>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { id: 'sla', label: 'SLA %', value: sla, set: setSla, placeholder: '99.99' },
            { id: 'regions', label: 'Regions', value: regions, set: setRegions, placeholder: '2' },
            { id: 'rto', label: 'RTO (min)', value: rto, set: setRto, placeholder: '15' },
            { id: 'rpo', label: 'RPO (min)', value: rpo, set: setRpo, placeholder: '5' },
          ].map((f) => (
            <div key={f.id}>
              <label htmlFor={f.id} className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{f.label}</label>
              <input
                id={f.id}
                type="number"
                value={f.value}
                onChange={(e) => f.set(e.target.value)}
                placeholder={f.placeholder}
                className="w-full rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>
          ))}
          <div className="col-span-2 sm:col-span-4">
            <label htmlFor="compliance" className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Compliance flags (comma-separated)</label>
            <input
              id="compliance"
              type="text"
              value={compliance}
              onChange={(e) => setCompliance(e.target.value)}
              placeholder="PCI-DSS, HIPAA, SOC2"
              className="w-full rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
        </div>
      </details>

      <button
        type="submit"
        disabled={loading || !description.trim()}
        className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
      >
        {loading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="32" strokeDashoffset="12"/>
            </svg>
            Generating…
          </>
        ) : (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            Generate architecture
          </>
        )}
      </button>
    </form>
  )
}
