import type { CSSProperties } from 'react'
import type { PlanNode } from '../types/api'

interface PlanTreeProps {
  node: PlanNode
  depth?: number
}

function metric(value: number | null, suffix = ''): string {
  return value === null ? '—' : `${value}${suffix}`
}

export function PlanTree({ node, depth = 0 }: PlanTreeProps) {
  return (
    <div className="plan-node" style={{ '--depth': depth } as CSSProperties}>
      <div className="plan-node__main">
        <span className="node-marker" aria-hidden="true">{depth === 0 ? '◈' : '↳'}</span>
        <div className="plan-node__title">
          <strong>{node.node_type}</strong>
          {node.relation && <span className="mono plan-node__relation">{node.relation}</span>}
        </div>
        <div className="plan-node__metrics">
          <span>actual <b>{metric(node.actual_total_time, ' ms')}</b></span>
          <span>rows <b>{metric(node.actual_rows)}</b></span>
          <span>loops <b>{metric(node.actual_loops)}</b></span>
        </div>
      </div>
      <div className="plan-node__details">
        <span>planned rows {metric(node.planned_rows)}</span>
        {node.index_name && <span>index <b className="mono">{node.index_name}</b></span>}
        {node.filter && <span className="plan-filter mono">filter: {node.filter}</span>}
        {node.sort_keys.length > 0 && <span>sort <b className="mono">{node.sort_keys.join(', ')}</b></span>}
        {node.buffers && <span>buffers hit/read <b>{node.buffers.shared_hit_blocks ?? 0}/{node.buffers.shared_read_blocks ?? 0}</b></span>}
      </div>
      {node.plans.length > 0 && (
        <div className="plan-node__children">
          {node.plans.map((child, index) => <PlanTree key={`${child.node_type}-${index}`} node={child} depth={depth + 1} />)}
        </div>
      )}
    </div>
  )
}
