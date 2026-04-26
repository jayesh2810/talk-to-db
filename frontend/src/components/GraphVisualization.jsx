import { useEffect, useState, useRef } from 'react'
import { useAuth } from '../context/AuthContext'

const NODE_COLORS = {
  customer: '#6366f1',
  product: '#8b5cf6',
  order: '#ec4899',
  item: '#f59e0b',
  interaction: '#10b981',
  campaign: '#f97316',
  unknown: '#6b7280',
}

const NODE_RADIUS = {
  customer: 10,
  product: 9,
  order: 6,
  item: 5,
  interaction: 5,
  campaign: 5,
  unknown: 5,
}

export default function GraphVisualization() {
  const { getAuthHeader, isAuthenticated } = useAuth()
  const [graphData, setGraphData] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [positions, setPositions] = useState({})
  const svgRef = useRef(null)

  const width = 900
  const height = 600

  useEffect(() => {
    if (!isAuthenticated) return

    const fetchData = async () => {
      try {
        setLoading(true)
        const headers = { ...getAuthHeader() }
        const [dataRes, statsRes] = await Promise.all([
          fetch('/api/graph/data?limit=150', { headers }),
          fetch('/api/graph/stats', { headers }),
        ])

        if (!dataRes.ok) throw new Error('Failed to fetch graph data')
        if (!statsRes.ok) throw new Error('Failed to fetch graph stats')

        const data = await dataRes.json()
        const statsData = await statsRes.json()

        setGraphData(data)
        setStats(statsData)
        setLoading(false)
      } catch (err) {
        setError(err.message)
        setLoading(false)
      }
    }

    fetchData()
    // Intentionally depend only on isAuthenticated; getAuthHeader reads latest credentials.
  }, [isAuthenticated])

  // Run a simple force simulation once graph data loads
  useEffect(() => {
    if (!graphData) return

    const nodes = graphData.nodes.map(n => ({
      ...n,
      x: Math.random() * width,
      y: Math.random() * height,
      vx: 0,
      vy: 0,
    }))

    const nodeMap = new Map(nodes.map(n => [n.id, n]))
    const edges = graphData.edges
      .map(e => ({ source: nodeMap.get(e.source), target: nodeMap.get(e.target), type: e.type }))
      .filter(e => e.source && e.target)

    const iterations = 300
    const repulsion = 1500
    const springLength = 80
    const springStrength = 0.05
    const centerStrength = 0.01
    const damping = 0.85

    for (let i = 0; i < iterations; i++) {
      // Repulsion between all nodes
      for (let a = 0; a < nodes.length; a++) {
        for (let b = a + 1; b < nodes.length; b++) {
          const dx = nodes[b].x - nodes[a].x
          const dy = nodes[b].y - nodes[a].y
          const distSq = dx * dx + dy * dy + 0.01
          const dist = Math.sqrt(distSq)
          const force = repulsion / distSq
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          nodes[a].vx -= fx
          nodes[a].vy -= fy
          nodes[b].vx += fx
          nodes[b].vy += fy
        }
      }

      // Spring forces along edges
      for (const e of edges) {
        const dx = e.target.x - e.source.x
        const dy = e.target.y - e.source.y
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.01
        const force = (dist - springLength) * springStrength
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        e.source.vx += fx
        e.source.vy += fy
        e.target.vx -= fx
        e.target.vy -= fy
      }

      // Gravity toward center + damping + integrate
      for (const n of nodes) {
        n.vx += (width / 2 - n.x) * centerStrength
        n.vy += (height / 2 - n.y) * centerStrength
        n.vx *= damping
        n.vy *= damping
        n.x += n.vx
        n.y += n.vy
        n.x = Math.max(20, Math.min(width - 20, n.x))
        n.y = Math.max(20, Math.min(height - 20, n.y))
      }
    }

    const pos = {}
    for (const n of nodes) pos[n.id] = { x: n.x, y: n.y }
    setPositions(pos)
  }, [graphData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">Loading graph data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400 text-sm">Error loading graph: {error}</div>
      </div>
    )
  }

  const nodeTypes = stats?.node_types || {}
  const edgeTypes = stats?.edge_types || {}

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-1">Graph Knowledge</h2>
        <p className="text-sm text-gray-400">
          Interactive visualization of the e-commerce knowledge graph
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Total Nodes</div>
          <div className="text-2xl font-bold text-white mt-1">{stats?.node_count ?? '—'}</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Total Edges</div>
          <div className="text-2xl font-bold text-white mt-1">{stats?.edge_count ?? '—'}</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Node Types</div>
          <div className="text-2xl font-bold text-white mt-1">{Object.keys(nodeTypes).length}</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Edge Types</div>
          <div className="text-2xl font-bold text-white mt-1">{Object.keys(edgeTypes).length}</div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-4">
        {Object.entries(nodeTypes).map(([type, count]) => (
          <div key={type} className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: NODE_COLORS[type] || NODE_COLORS.unknown }}
            />
            <span className="text-xs text-gray-300 capitalize">{type}</span>
            <span className="text-xs text-gray-500 font-mono">{count}</span>
          </div>
        ))}
      </div>

      {/* Graph SVG */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <svg
          ref={svgRef}
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="bg-gray-950"
        >
          {/* Edges */}
          <g>
            {graphData?.edges?.map((edge, idx) => {
              const source = positions[edge.source]
              const target = positions[edge.target]
              if (!source || !target) return null
              const isHighlighted =
                hoveredNode && (edge.source === hoveredNode || edge.target === hoveredNode)
              return (
                <line
                  key={idx}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={isHighlighted ? '#818cf8' : '#374151'}
                  strokeWidth={isHighlighted ? 1.5 : 0.5}
                  opacity={hoveredNode && !isHighlighted ? 0.2 : 0.6}
                />
              )
            })}
          </g>

          {/* Nodes */}
          <g>
            {graphData?.nodes?.map((node) => {
              const pos = positions[node.id]
              if (!pos) return null
              const isHovered = hoveredNode === node.id
              const radius = NODE_RADIUS[node.type] || 5
              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{ cursor: 'pointer' }}
                >
                  <circle
                    r={isHovered ? radius + 2 : radius}
                    fill={NODE_COLORS[node.type] || NODE_COLORS.unknown}
                    stroke={isHovered ? '#fff' : 'transparent'}
                    strokeWidth={2}
                    opacity={hoveredNode && !isHovered ? 0.4 : 1}
                  />
                  {(isHovered || node.type === 'customer' || node.type === 'product') && (
                    <text
                      y={-radius - 4}
                      textAnchor="middle"
                      fontSize="10"
                      fill="#e5e7eb"
                      style={{ pointerEvents: 'none', fontWeight: isHovered ? 600 : 400 }}
                    >
                      {node.label}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        </svg>
      </div>

      <p className="text-xs text-gray-500 mt-3">
        Showing {graphData?.nodes?.length ?? 0} of {stats?.node_count ?? 0} nodes and{' '}
        {graphData?.edges?.length ?? 0} edges. Hover over a node to explore its connections.
      </p>
    </div>
  )
}
