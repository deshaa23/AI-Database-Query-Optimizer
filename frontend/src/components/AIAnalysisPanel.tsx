import type { OptimizationAnalysis } from '../types/api'

export function AIAnalysisPanel({ analysis }: { analysis: OptimizationAnalysis | null }) {
  if (!analysis) {
    return <div className="muted-state"><span className="state-icon">◎</span><span>AI reasoning is off for this run. Enable it to rank deterministic candidates and discuss tradeoffs.</span></div>
  }

  return (
    <div className="ai-panel">
      <div className="ai-panel__summary"><span className="ai-spark">✦</span><p>{analysis.summary}</p><span className="confidence-pill">{Math.round(analysis.confidence * 100)}% confidence</span></div>
      {analysis.primary_recommendation && <div className="primary-recommendation"><span className="eyebrow">Primary recommendation</span><strong>{analysis.primary_recommendation}</strong></div>}
      <div className="ai-columns">
        <div><span className="eyebrow">Tradeoffs</span><ul>{analysis.tradeoffs.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><span className="eyebrow">Validation steps</span><ol>{analysis.validation_steps.map((item) => <li key={item}>{item}</li>)}</ol></div>
      </div>
      {analysis.ranked_recommendations.length > 0 && <div className="ranked-list"><span className="eyebrow">Ranked reasoning</span>{analysis.ranked_recommendations.map((item, index) => <div className="ranked-item" key={`${item.title}-${index}`}><span className="rank">0{index + 1}</span><div><strong>{item.title}</strong><p>{item.explanation}</p></div></div>)}</div>}
    </div>
  )
}
