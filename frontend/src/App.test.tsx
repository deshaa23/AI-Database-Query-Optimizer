import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const response = {
  query: 'SELECT id FROM orders WHERE user_id = 4242',
  execution_plan: {
    query: 'SELECT id FROM orders WHERE user_id = 4242',
    planning_time_ms: 0.2,
    execution_time_ms: 4.2,
    observations: [],
    plan: {
      node_type: 'Seq Scan', relation: 'orders', startup_cost: 0, total_cost: 10,
      actual_startup_time: 0.1, actual_total_time: 4.2, planned_rows: 10,
      actual_rows: 12, actual_loops: 1, index_name: null, filter: 'user_id = 4242',
      sort_keys: [], buffers: { shared_hit_blocks: 10, shared_read_blocks: 0, shared_dirtied_blocks: 0, shared_written_blocks: 0, local_hit_blocks: 0, local_read_blocks: 0, local_dirtied_blocks: 0, local_written_blocks: 0, temp_read_blocks: 0, temp_written_blocks: 0 }, plans: [],
    },
  },
  observations: [{ type: 'sequential_scan', severity: 'medium', message: 'Sequential scan detected.', node_type: 'Seq Scan', relation: 'orders' }],
  deterministic_recommendations: [{ type: 'MISSING_INDEX_CANDIDATE', severity: 'medium', title: 'Consider an index', description: 'A filtered scan was found.', rationale: 'Evidence supports review.', evidence: ['Filter: user_id = 4242'], affected_table: 'orders', affected_columns: ['user_id'], suggested_sql: 'CREATE INDEX idx_orders_user_id ON orders(user_id);', confidence: 0.8 }],
  ai_analysis: { summary: 'Grounded reasoning.', primary_recommendation: 'Review the index candidate.', ranked_recommendations: [], tradeoffs: ['Write overhead'], confidence: 0.7, validation_steps: ['Run EXPLAIN ANALYZE'] },
  benchmark: { original_query: 'SELECT id FROM orders WHERE user_id = 4242', candidate_type: 'MISSING_INDEX_CANDIDATE', candidate_table: 'orders', candidate_columns: ['user_id'], candidate_index_name: 'queryforge_benchmark_idx_orders_user_id', repetitions: 2, warmup_runs: 0, baseline: { execution_times_ms: [8, 9], median_execution_time_ms: 8.5, mean_execution_time_ms: 8.5, planning_times_ms: [0.2], median_planning_time_ms: 0.2, node_type: 'Seq Scan', relation_name: 'orders', index_name: null, actual_rows: 12, planned_rows: 10, shared_hit_blocks: 10, shared_read_blocks: 0 }, after: { execution_times_ms: [3, 4], median_execution_time_ms: 3.5, mean_execution_time_ms: 3.5, planning_times_ms: [0.1], median_planning_time_ms: 0.1, node_type: 'Index Scan', relation_name: 'orders', index_name: 'queryforge_benchmark_idx_orders_user_id', actual_rows: 12, planned_rows: 10, shared_hit_blocks: 4, shared_read_blocks: 0 }, comparison: { baseline_median_execution_time_ms: 8.5, after_median_execution_time_ms: 3.5, execution_time_delta_ms: -5, improvement_percent: 58.8, classification: 'improved', scan_type_changed: true }, cleanup_completed: true },
  benchmark_note: null,
}

function mockSuccess() {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

test('shows the empty state and sample query', () => {
  render(<App />)
  expect(screen.getByText('Ready when you are.')).toBeInTheDocument()
  expect(screen.getByLabelText('PostgreSQL SELECT query')).toHaveValue(
    'SELECT id, created_at\nFROM orders\nWHERE user_id = 4242\nORDER BY created_at DESC;',
  )
})

test('edits query, toggles options, and renders analysis results', async () => {
  const user = userEvent.setup()
  mockSuccess()
  render(<App />)
  const editor = screen.getByLabelText('PostgreSQL SELECT query')
  await user.clear(editor)
  await user.type(editor, 'SELECT 1')
  await user.click(screen.getByLabelText('Run benchmark (slower)'))
  await user.click(screen.getByRole('button', { name: /Analyze query/ }))
  await waitFor(() => expect(screen.getByText('Analysis overview')).toBeInTheDocument())
  expect(screen.getByText('Consider an index')).toBeInTheDocument()
  expect(screen.getByText('Grounded reasoning.')).toBeInTheDocument()
  expect(screen.getByText('Performance benchmark')).toBeInTheDocument()
})

test('copies suggested SQL and displays API errors', async () => {
  const user = userEvent.setup()
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  mockSuccess()
  render(<App />)
  await user.click(screen.getByRole('button', { name: /Analyze query/ }))
  await waitFor(() => expect(screen.getByText('Suggested SQL · review only')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Copy SQL' }))
  expect(writeText).toHaveBeenCalledWith('CREATE INDEX idx_orders_user_id ON orders(user_id);')

  vi.restoreAllMocks()
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'))
  await user.click(screen.getByRole('button', { name: /Analyze query/ }))
  await waitFor(() => expect(screen.getByText('Could not connect to the QueryForge API.')).toBeInTheDocument())
})
