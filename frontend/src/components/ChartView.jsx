import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const COLORS = ['#2563eb', '#0d9488', '#d97706', '#db2777', '#7c3aed', '#64748b']

const compact = (v) =>
  typeof v === 'number' ? new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(v) : v
const full = (v) => (typeof v === 'number' ? v.toLocaleString('en', { maximumFractionDigits: 2 }) : v)

export default function ChartView({ chart, rows }) {
  if (!chart || !rows?.length) return null
  const { type, x_key: x, y_key: y, title } = chart
  const data = rows.map((r) => ({ ...r, [x]: String(r[x] ?? '—'), [y]: Number(r[y]) || 0 }))

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <ResponsiveContainer width="100%" height={280}>
        {type === 'line' ? (
          <LineChart data={data} margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
            <XAxis dataKey={x} tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={compact} tick={{ fontSize: 11 }} width={56} />
            <Tooltip formatter={full} />
            <Line type="monotone" dataKey={y} stroke={COLORS[0]} strokeWidth={2} dot={false} />
          </LineChart>
        ) : type === 'pie' ? (
          <PieChart>
            <Tooltip formatter={full} />
            <Pie data={data} dataKey={y} nameKey={x} outerRadius={100} label={(d) => d[x]}>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
            <XAxis type="number" tickFormatter={compact} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey={x} width={170} tick={{ fontSize: 11 }}
              tickFormatter={(v) => (v.length > 26 ? `${v.slice(0, 25)}…` : v)} />
            <Tooltip formatter={full} />
            <Bar dataKey={y} fill={COLORS[0]} radius={[0, 4, 4, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </figure>
  )
}
