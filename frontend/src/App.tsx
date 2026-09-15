import { useState } from 'react'
import { AIAnalysisPanel } from './components/AIAnalysisPanel'
import { BenchmarkPanel } from './components/BenchmarkPanel'
import { PlanTree } from './components/PlanTree'
import { RecommendationCard } from './components/RecommendationCard'
import { analyzeQuery, ApiError } from './services/api'
import type { AnalyzeResponse } from './types/api'

const SAMPLE_QUERY = 'SELECT id, created_at\nFROM orders\nWHERE user_id = 4242\nORDER BY created_at DESC;'

function formatMetric(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(2)} ms`
}

function App() {
  const [query, setQuery] = useState(SAMPLE_QUERY)
  const [includeAi, setIncludeAi] = useState(true)
  const [includeBenchmark, setIncludeBenchmark] = useState(false)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!query.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      setResult(await analyzeQuery({ query, include_ai: includeAi, include_benchmark: includeBenchmark }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong while analyzing the query.')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault()
      void submit()
    }
  }

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="/" aria-label="QueryForge home"><span className="brand-mark">QF</span><span>QueryForge <em>AI</em></span></a><div className="topbar-status"><span className="status-dot" />Local analysis workspace <span className="version">M10</span></div></header>
    <main className="workspace">
      <section className="hero"><div><span className="kicker">PostgreSQL observability</span><h1>Find the work<br /><i>behind</i> your query.</h1><p>Turn execution plans into clear, measurable decisions. QueryForge keeps the evidence visible from the first scan to the final recommendation.</p></div><div className="hero-stamp"><span>QUERY / PLAN / PROVE</span><strong>01</strong><small>SELECT analysis</small></div></section>
      <section className="query-panel section-panel"><div className="panel-header"><div><span className="eyebrow">01 · Input</span><h2>SQL Query</h2></div><button className="text-button" type="button" onClick={() => setQuery(SAMPLE_QUERY)}>Load sample ↗</button></div><label className="sr-only" htmlFor="query-input">PostgreSQL SELECT query</label><textarea id="query-input" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={handleKeyDown} spellCheck={false} aria-describedby="query-help" /><div className="query-footer"><span id="query-help"><kbd>Ctrl</kbd><span>+</span><kbd>Enter</kbd> to analyze</span><div className="controls"><label className="toggle"><input type="checkbox" checked={includeAi} onChange={(event) => setIncludeAi(event.target.checked)} /><span className="toggle-track" /><span>AI reasoning</span></label><label className="toggle"><input type="checkbox" checked={includeBenchmark} onChange={(event) => setIncludeBenchmark(event.target.checked)} /><span className="toggle-track" /><span>Run benchmark <small>(slower)</small></span></label><button className="analyze-button" type="button" onClick={() => void submit()} disabled={loading || !query.trim()}>{loading ? <><span className="spinner" />Analyzing</> : <>Analyze query <span>→</span></>}</button></div></div></section>
      {error && <div className="error-banner" role="alert"><strong>Analysis failed</strong><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}
      {result?.ai_note && <div className="info-banner" role="status"><strong>Analysis completed</strong><span>{result.ai_note}</span></div>}
      {!result && !loading && !error && <section className="empty-state"><div className="empty-grid" /><span className="empty-icon">⌁</span><h2>Ready when you are.</h2><p>Enter a PostgreSQL SELECT query to inspect its execution plan and discover optimization opportunities.</p><button type="button" className="outline-button" onClick={() => void submit()}>Analyze the sample query <span>→</span></button></section>}
      {loading && <section className="loading-state"><span className="spinner large" /><div><strong>Reading the execution plan</strong><p>PostgreSQL is measuring the query. This can take a moment.</p></div></section>}
      {result && !loading && <AnalysisDashboard result={result} />}
    </main>
    <footer className="footer"><span>QueryForge AI · SQL performance workspace</span><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API docs ↗</a></footer>
  </div>
}

function AnalysisDashboard({ result }: { result: AnalyzeResponse }) {
  const plan = result.execution_plan
  return <div className="results-stack">
    <section className="overview-section"><div className="section-heading"><div><span className="eyebrow">02 · Signal</span><h2>Analysis overview</h2></div><span className="run-query mono">{result.query.replace(/\s+/g, ' ').slice(0, 72)}{result.query.length > 72 ? '…' : ''}</span></div><div className="overview-grid"><div className="metric-card accent"><span>Execution time</span><strong>{formatMetric(plan.execution_time_ms)}</strong><small>measured by PostgreSQL</small></div><div className="metric-card"><span>Planning time</span><strong>{formatMetric(plan.planning_time_ms)}</strong><small>query planning phase</small></div><div className="metric-card"><span>Observations</span><strong>{result.observations.length.toString().padStart(2, '0')}</strong><small>plan signals detected</small></div><div className="metric-card"><span>Recommendations</span><strong>{result.deterministic_recommendations.length.toString().padStart(2, '0')}</strong><small>deterministic candidates</small></div></div></section>
    <section className="section-panel plan-section"><div className="section-heading"><div><span className="eyebrow">03 · Structure</span><h2>Execution plan</h2></div><span className="plan-legend"><span className="legend-line" /> recursive node tree</span></div><PlanTree node={plan.plan} /></section>
    <section className="observations-section"><div className="section-heading"><div><span className="eyebrow">04 · Diagnostics</span><h2>Observed signals</h2></div></div><div className="observation-list">{result.observations.length === 0 ? <div className="muted-state">No additional observations were reported for this plan.</div> : result.observations.map((observation, index) => <article className="observation" key={`${observation.type}-${index}`}><span className={`observation-icon severity-${observation.severity}`}>{observation.severity === 'high' ? '!' : '•'}</span><div><div className="observation-title"><strong>{observation.message}</strong><span className={`severity severity-${observation.severity}`}>{observation.severity}</span></div><span className="observation-context">{observation.node_type}{observation.relation ? ` · ${observation.relation}` : ''}</span></div></article>)}</div></section>
    <section className="recommendations-section"><div className="section-heading"><div><span className="eyebrow">05 · Action</span><h2>Optimization recommendations</h2></div><span className="grounded-badge">● grounded in plan evidence</span></div><div className="recommendation-grid">{result.deterministic_recommendations.length === 0 ? <div className="muted-state">No deterministic recommendations for this plan.</div> : result.deterministic_recommendations.map((recommendation, index) => <RecommendationCard recommendation={recommendation} key={`${recommendation.type}-${index}`} />)}</div></section>
    <section className="section-panel ai-section"><div className="section-heading"><div><span className="eyebrow">06 · Reasoning</span><h2>AI analysis</h2></div><span className="ai-label">✦ grounded assistant</span></div><AIAnalysisPanel analysis={result.ai_analysis} /></section>
    <section className="section-panel benchmark-section"><div className="section-heading"><div><span className="eyebrow">07 · Proof</span><h2>Performance benchmark</h2></div><span className="benchmark-note">controlled · before / after</span></div><BenchmarkPanel benchmark={result.benchmark} note={result.benchmark_note} /></section>
  </div>
}

export default App
