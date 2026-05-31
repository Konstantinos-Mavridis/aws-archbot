'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  diagram: string
}

export default function MermaidDiagram({ diagram }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [raw, setRaw] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function render() {
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'loose' })
        const { svg } = await mermaid.render(`archbot-diagram-${Date.now()}`, diagram)
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg
        }
      } catch (err) {
        if (!cancelled) setError(String(err))
      }
    }
    render()
    return () => { cancelled = true }
  }, [diagram])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-400 dark:text-gray-500">
          This diagram renders natively in GitHub Markdown via the \`\`\`mermaid code fence.
        </p>
        <button
          onClick={() => setRaw((v) => !v)}
          className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline transition-colors"
        >
          {raw ? 'Show diagram' : 'Show source'}
        </button>
      </div>

      {raw ? (
        <pre className="text-xs font-mono bg-gray-50 dark:bg-gray-950 rounded-lg border border-gray-200 dark:border-gray-800 p-4 overflow-x-auto whitespace-pre-wrap">
          <code>{diagram}</code>
        </pre>
      ) : error ? (
        <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="font-medium">Diagram render error:</p>
          <pre className="text-xs mt-1 whitespace-pre-wrap">{error}</pre>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="mermaid bg-gray-50 dark:bg-gray-950 rounded-lg border border-gray-200 dark:border-gray-800 p-4 overflow-x-auto min-h-[120px] flex items-center justify-center"
        />
      )}
    </div>
  )
}
