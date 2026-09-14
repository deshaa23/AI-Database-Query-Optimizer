import { useState } from 'react'
import type { OptimizationRecommendation } from '../types/api'

interface RecommendationCardProps {
  recommendation: OptimizationRecommendation
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const [copied, setCopied] = useState(false)
  const copySql = async () => {
    if (!recommendation.suggested_sql) return
    await navigator.clipboard.writeText(recommendation.suggested_sql)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <article className="recommendation-card">
      <div className="card-heading">
        <div>
          <span className={`eyebrow recommendation-type type-${recommendation.type.toLowerCase()}`}>{recommendation.type.replaceAll('_', ' ')}</span>
          <h3>{recommendation.title}</h3>
        </div>
        <span className={`severity severity-${recommendation.severity}`}>{recommendation.severity}</span>
      </div>
      <p>{recommendation.description}</p>
      <p className="rationale"><b>Why it surfaced</b> {recommendation.rationale}</p>
      {(recommendation.affected_table || recommendation.affected_columns.length > 0) && (
        <div className="tag-row">
          {recommendation.affected_table && <span className="tag mono">table: {recommendation.affected_table}</span>}
          {recommendation.affected_columns.map((column) => <span className="tag mono" key={column}>column: {column}</span>)}
          <span className="tag">confidence: {Math.round(recommendation.confidence * 100)}%</span>
        </div>
      )}
      {recommendation.evidence.length > 0 && <div className="evidence">{recommendation.evidence.map((item) => <span key={item}>{item}</span>)}</div>}
      {recommendation.suggested_sql && (
        <div className="sql-suggestion">
          <div className="code-label"><span>Suggested SQL · review only</span><button type="button" className="copy-button" onClick={copySql}>{copied ? 'Copied' : 'Copy SQL'}</button></div>
          <code>{recommendation.suggested_sql}</code>
        </div>
      )}
    </article>
  )
}
