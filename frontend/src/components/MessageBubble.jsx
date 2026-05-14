import React from 'react'
import QueryDisplay from './QueryDisplay'
import TraversalSteps from './TraversalSteps'
import ResultTable from './ResultTable'

function AgentStageCard({ message, onAgentAction }) {
  const stageLabel = {
    draft_plan: 'Plan Draft',
    final_actions: 'Final Actions',
    completed: 'Completed',
  }[message.stage] || 'Agent Workflow'

  const labelize = (s) => String(s || '').replace(/_/g, ' ')

  const kvTable = (obj) => (
    <div className="mt-2 overflow-x-auto border border-slate-700 rounded-lg">
      <table className="w-full text-xs">
        <tbody>
          {Object.entries(obj || {}).map(([k, v]) => (
            <tr key={k} className="border-b border-slate-700/60 last:border-b-0">
              <td className="px-3 py-2 text-slate-400 font-semibold uppercase tracking-wide whitespace-nowrap">{labelize(k)}</td>
              <td className="px-3 py-2 text-slate-200">{typeof v === 'number' ? v.toLocaleString() : String(v ?? '')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const listTable = (rows) => {
    if (!Array.isArray(rows) || rows.length === 0) return null
    const cols = Object.keys(rows[0] || {})
    return (
      <div className="mt-2 overflow-x-auto border border-slate-700 rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-slate-900/70">
            <tr className="border-b border-slate-700/60">
              {cols.map((c) => (
                <th key={c} className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide whitespace-nowrap">
                  {labelize(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 8).map((row, i) => (
              <tr key={i} className="border-b border-slate-700/60 last:border-b-0">
                {cols.map((c) => (
                  <td key={c} className="px-3 py-2 text-slate-200 whitespace-nowrap">
                    {typeof row[c] === 'number' ? row[c].toLocaleString() : String(row[c] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderProposal = () => {
    if (!message.proposal) return null
    if (message.proposal.plan) {
      const plan = message.proposal.plan
      return (
        <div className="mt-2">
          {kvTable({
            objective: plan.objective,
            goal_type: plan.goal_type,
            success_metric: plan.success_metric || '',
            needs_clarification: plan.needs_clarification || false,
            plan_rationale: plan.plan_rationale || '',
            revision_note: plan.revision_note || '',
          })}
          {Array.isArray(plan.steps) && plan.steps.length > 0 && (
            <ol className="mt-2 list-decimal list-inside text-xs text-slate-200 space-y-1">
              {plan.steps.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          )}
          {Array.isArray(plan.tool_steps) && plan.tool_steps.length > 0 && (
            <>
              <div className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Planned Tool Steps</div>
              {listTable(plan.tool_steps)}
            </>
          )}
        </div>
      )
    }
    if (message.proposal.final_actions) return listTable(message.proposal.final_actions)
    return kvTable(message.proposal)
  }

  const renderExecutionSummary = () => {
    if (!message.execution_summary) return null
    const ex = message.execution_summary
    const top = ex.top_candidates
    const support = ex.supporting_rows
    const scalar = {
      avg_top_score: ex.avg_top_score,
      estimated_goal_movement_pct: ex.estimated_goal_movement_pct,
    }
    return (
      <div className="mt-2">
        {kvTable(scalar)}
        {ex.risk_buckets && (
          <>
            <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Risk Buckets</div>
            {kvTable(ex.risk_buckets)}
          </>
        )}
        {Array.isArray(top) && top.length > 0 && (
          <>
            <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Top Candidates</div>
            {listTable(top)}
          </>
        )}
        {Array.isArray(support) && support.length > 0 && (
          <>
            <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Supporting Rows</div>
            {listTable(support)}
          </>
        )}
      </div>
    )
  }

  const renderAgentLogs = () => {
    const logs = Array.isArray(message.agent_logs) ? message.agent_logs : []
    if (!logs.length) return null
    return (
      <div className="mt-3">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Agent Logs</div>
        <div className="mt-1 overflow-x-auto border border-slate-700 rounded-lg">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/70">
              <tr className="border-b border-slate-700/60">
                <th className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide">Time</th>
                <th className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide">Source</th>
                <th className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide">Event</th>
                <th className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide">Detail</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(-20).map((l, i) => (
                <tr key={i} className="border-b border-slate-700/60 last:border-b-0">
                  <td className="px-3 py-2 text-slate-300 whitespace-nowrap">{String(l.time || '')}</td>
                  <td className="px-3 py-2 text-slate-300 whitespace-nowrap">{String(l.source || '')}</td>
                  <td className="px-3 py-2 text-slate-200 whitespace-nowrap">{String(l.event || '')}</td>
                  <td className="px-3 py-2 text-slate-200">{String(l.detail || '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-indigo-950/30 border border-indigo-700/40 rounded-2xl px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-bold uppercase tracking-wider text-indigo-300">{stageLabel}</div>
        {message.workflow_id && (
          <div className="text-[10px] font-mono text-indigo-400/90">#{message.workflow_id}</div>
        )}
      </div>
      <p className="mt-2 text-sm text-slate-200 leading-relaxed">{message.summary || message.content}</p>
      {renderProposal()}
      {renderExecutionSummary()}
      {renderAgentLogs()}
      {message.pending_approval && (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => onAgentAction?.('approve', message)}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 transition-colors"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => onAgentAction?.('revise', message)}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 transition-colors"
          >
            Revise
          </button>
        </div>
      )}
    </div>
  )
}

export default function MessageBubble({ message, onCustomerClick, onAgentAction }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-xl bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-lg shadow-indigo-600/20">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start mb-8">
      <div className="max-w-4xl w-full space-y-4">
        <div className="flex items-center gap-2 px-1">
          <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 shadow-sm">
            K
          </div>
          <span className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Intelligence Engine</span>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl px-4 py-3 shadow-sm">
          {message.mode === 'agent_goal' ? (
            <AgentStageCard message={message} onAgentAction={onAgentAction} />
          ) : (
            <p className="text-sm text-slate-200 leading-relaxed">
              {message.summary || message.content}
            </p>
          )}
        </div>

        {message.mode !== 'agent_goal' && message.pql_query && (
          <div className="transition-all duration-300">
            <QueryDisplay pqlQuery={message.pql_query} queryType={message.query_type} />
          </div>
        )}

        {message.mode !== 'agent_goal' && message.traversal_steps && message.traversal_steps.length > 0 && (
          <div className="transition-all duration-300">
            <TraversalSteps steps={message.traversal_steps} />
          </div>
        )}

        {message.mode !== 'agent_goal' && message.results && message.results.length > 0 && (
          <div className="transition-all duration-300">
            <ResultTable
              results={message.results}
              columns={message.columns || []}
              queryType={message.query_type}
              totalResults={message.total_results || message.results.length}
              onCustomerClick={onCustomerClick}
            />
          </div>
        )}
      </div>
    </div>
  )
}
