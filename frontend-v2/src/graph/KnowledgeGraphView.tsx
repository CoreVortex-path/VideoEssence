import { useAppStore } from '../store/appStore'

interface GraphNode {
  id: string
  label: string
  x: number
  y: number
  color: string
}

const NODES: GraphNode[] = [
  { id: 'transformer', label: 'Transformer', x: 400, y: 120, color: 'var(--accent)' },
  { id: 'attention', label: 'Attention', x: 180, y: 300, color: 'var(--amber)' },
  { id: 'scaling', label: 'Scaling', x: 620, y: 300, color: 'var(--purple)' },
  { id: 'emergence', label: 'Emergence', x: 400, y: 430, color: 'var(--cyan)' },
]

const EDGES: [string, string][] = [
  ['transformer', 'attention'],
  ['transformer', 'scaling'],
  ['attention', 'emergence'],
  ['scaling', 'emergence'],
  ['attention', 'scaling'],
]

const byId = new Map(NODES.map((n) => [n.id, n]))

/** Статичный SVG-граф знаний (мок, без API). */
export default function KnowledgeGraphView() {
  const setMainView = useAppStore((s) => s.setMainView)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-border-glass px-3 py-2">
        <button
          type="button"
          onClick={() => setMainView('player')}
          className="rounded px-2 py-1 text-[12px] text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary"
        >
          ← Back to Player
        </button>
        <span className="text-[12px] text-text-faint">Knowledge Graph (mock)</span>
      </div>

      <div className="flex min-h-0 flex-1 items-center justify-center p-4">
        <svg
          viewBox="0 0 800 500"
          className="h-full max-h-full w-full max-w-[800px]"
          role="img"
          aria-label="Knowledge graph"
        >
          {EDGES.map(([from, to]) => {
            const a = byId.get(from)!
            const b = byId.get(to)!
            return (
              <line
                key={`${from}-${to}`}
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="var(--border-primary)"
                strokeWidth="1.5"
              />
            )
          })}
          {NODES.map((n) => (
            <g
              key={n.id}
              className="graph-node cursor-pointer"
              style={{ transformOrigin: `${n.x}px ${n.y}px` }}
              onClick={() => console.log('[Graph] node click:', n.id)}
            >
              <circle
                cx={n.x} cy={n.y} r="34"
                fill="var(--bg-secondary)"
                stroke={n.color}
                strokeWidth="2.5"
                className="graph-node-circle"
              />
              <circle cx={n.x} cy={n.y} r="6" fill={n.color} />
              <text
                x={n.x} y={n.y + 52}
                textAnchor="middle"
                fill="var(--text-secondary)"
                fontSize="14"
              >
                {n.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  )
}
