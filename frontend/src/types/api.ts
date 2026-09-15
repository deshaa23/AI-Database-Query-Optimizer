export type Severity = 'low' | 'medium' | 'high'
export type RecommendationType = 'MISSING_INDEX_CANDIDATE' | 'PERFORMANCE_BOTTLENECK'
export type BenchmarkClassification = 'improved' | 'regressed' | 'no_meaningful_change'

export interface PlanNode {
  node_type: string
  relation: string | null
  startup_cost: number | null
  total_cost: number | null
  actual_startup_time: number | null
  actual_total_time: number | null
  planned_rows: number | null
  actual_rows: number | null
  actual_loops: number | null
  index_name: string | null
  filter: string | null
  sort_keys: string[]
  buffers: BufferInfo | null
  plans: PlanNode[]
}

export interface BufferInfo {
  shared_hit_blocks: number | null
  shared_read_blocks: number | null
  shared_dirtied_blocks: number | null
  shared_written_blocks: number | null
  local_hit_blocks: number | null
  local_read_blocks: number | null
  local_dirtied_blocks: number | null
  local_written_blocks: number | null
  temp_read_blocks: number | null
  temp_written_blocks: number | null
}

export interface PlanObservation {
  type: string
  severity: Severity
  message: string
  node_type: string | null
  relation: string | null
}

export interface ExplainResult {
  query: string
  plan: PlanNode
  planning_time_ms: number | null
  execution_time_ms: number | null
  observations: PlanObservation[]
}

export interface OptimizationRecommendation {
  type: RecommendationType
  severity: Severity
  title: string
  description: string
  rationale: string
  evidence: string[]
  affected_table: string | null
  affected_columns: string[]
  suggested_sql: string | null
  confidence: number
}

export interface AIRecommendation {
  recommendation_type: RecommendationType
  title: string
  explanation: string
  rationale: string
  affected_table: string | null
  affected_columns: string[]
  suggested_sql: string | null
  confidence: number
}

export interface OptimizationAnalysis {
  summary: string
  primary_recommendation: string | null
  ranked_recommendations: AIRecommendation[]
  tradeoffs: string[]
  confidence: number
  validation_steps: string[]
}

export interface BenchmarkMeasurement {
  execution_times_ms: number[]
  median_execution_time_ms: number | null
  mean_execution_time_ms: number | null
  planning_times_ms: number[]
  median_planning_time_ms: number | null
  node_type: string | null
  relation_name: string | null
  index_name: string | null
  actual_rows: number | null
  planned_rows: number | null
  shared_hit_blocks: number | null
  shared_read_blocks: number | null
}

export interface BenchmarkComparison {
  baseline_median_execution_time_ms: number | null
  after_median_execution_time_ms: number | null
  execution_time_delta_ms: number | null
  improvement_percent: number | null
  classification: BenchmarkClassification
  scan_type_changed: boolean
}

export interface BenchmarkResult {
  original_query: string
  candidate_type: string
  candidate_table: string
  candidate_columns: string[]
  candidate_index_name: string
  repetitions: number
  warmup_runs: number
  baseline: BenchmarkMeasurement
  after: BenchmarkMeasurement
  comparison: BenchmarkComparison
  cleanup_completed: boolean
}

export interface AnalyzeRequest {
  query: string
  include_ai: boolean
  include_benchmark: boolean
}

export interface AnalyzeResponse {
  query: string
  execution_plan: ExplainResult
  observations: PlanObservation[]
  deterministic_recommendations: OptimizationRecommendation[]
  ai_analysis: OptimizationAnalysis | null
  ai_note: string | null
  benchmark: BenchmarkResult | null
  benchmark_note: string | null
}
