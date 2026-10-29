import { useState } from 'react'

function ResultTable({ rows }) {
  if (!rows?.length) return <p className="muted">No rows returned.</p>
  const cols = Object.keys(rows[0])
  const fmt = (v) =>
    typeof v === 'number' ? v.toLocaleString('en', { maximumFractionDigits: 2 })
      : typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v ?? '')
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.slice(0, 20).map((r, i) => (
            <tr key={i}>{cols.map((c) => <td key={c}>{fmt(r[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
      {rows.length > 20 && <p className="muted">Showing 20 of {rows.length} rows.</p>}
    </div>
  )
}

/** Shows how the agent got its answer: every generated pipeline, its result or error. */
export default function Trace({ steps }) {
  const [open, setOpen] = useState(false)
  if (!steps?.length) return null
  const failed = steps.filter((s) => s.error).length

  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen(!open)}>
        {open ? '▾' : '▸'} {steps.length} MongoDB {steps.length === 1 ? 'query' : 'queries'}
        {failed > 0 && <span className="badge warn">{failed} self-corrected</span>}
      </button>
      {open && steps.map((s, i) => (
        <div key={i} className={`step ${s.error ? 'step-error' : ''}`}>
          <div className="step-head">
            <strong>Step {i + 1}</strong>
            <span className="muted">{s.error ? 'failed' : `${s.row_count} rows`} · {s.duration_ms} ms</span>
          </div>
          <p className="step-reason">{s.reasoning}</p>
          <pre>{`db.purchases.aggregate(${JSON.stringify(s.pipeline, null, 2)})`}</pre>
          {s.error ? <p className="error">{s.error}</p> : <ResultTable rows={s.rows} />}
        </div>
      ))}
    </div>
  )
}
