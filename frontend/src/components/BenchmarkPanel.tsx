import type { BenchmarkResult } from '../types/api'

function formatMs(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(2)} ms`
}

export function BenchmarkPanel({ benchmark, note }: { benchmark: BenchmarkResult | null; note: string | null }) {
  if (!benchmark) return <div className="muted-state"><span className="state-icon">⌁</span><span>{note ?? 'Benchmarking was not requested for this analysis.'}</span></div>
  const comparison = benchmark.comparison
  return <div className="benchmark-panel">
    <div className="benchmark-metrics">
      <div><span>Baseline median</span><strong>{formatMs(comparison.baseline_median_execution_time_ms)}</strong></div>
      <div><span>After median</span><strong>{formatMs(comparison.after_median_execution_time_ms)}</strong></div>
      <div><span>Measured change</span><strong className={`change-${comparison.classification}`}>{comparison.improvement_percent === null ? '—' : `${comparison.improvement_percent.toFixed(1)}%`}</strong></div>
    </div>
    <div className="benchmark-meta"><span className={`classification classification-${comparison.classification}`}>{comparison.classification.replaceAll('_', ' ')}</span><span>delta {formatMs(comparison.execution_time_delta_ms)}</span><span>scan changed {comparison.scan_type_changed ? 'yes' : 'no'}</span><span>{benchmark.repetitions} measured runs · {benchmark.warmup_runs} warmup</span></div>
    <div className="measurement-grid"><div><span className="eyebrow">Before</span><p className="mono">{benchmark.baseline.node_type} · {benchmark.baseline.relation_name ?? 'unknown relation'}</p></div><div><span className="eyebrow">After</span><p className="mono">{benchmark.after.node_type} · {benchmark.after.relation_name ?? 'unknown relation'}</p></div></div>
  </div>
}
