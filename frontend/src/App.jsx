import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getExamples, getHealth, sendMessage } from './api'
import ChartView from './components/ChartView'
import Trace from './components/Trace'

const newSession = () => crypto.randomUUID()

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [examples, setExamples] = useState([])
  const [health, setHealth] = useState(null)
  const [sessionId, setSessionId] = useState(newSession)
  const endRef = useRef(null)

  useEffect(() => {
    getExamples().then(setExamples).catch(() => {})
    getHealth().then(setHealth).catch((e) => setHealth({ status: 'down', error: e.message }))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function ask(text) {
    const question = text.trim()
    if (!question || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: question }])
    setLoading(true)
    try {
      const res = await sendMessage(question, sessionId)
      setMessages((m) => [...m, { role: 'assistant', content: res.answer, chart: res.chart,
        chartRows: res.chart_rows, steps: res.steps }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `⚠️ ${e.message}`, error: true }])
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setMessages([])
    setSessionId(newSession())
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Procurement<br />Assistant</h1>
        <p className="muted">Ask questions about 346k State of California purchase-order line items (FY 2012–2015).</p>
        <div className={`status ${health?.status === 'ok' ? 'ok' : 'down'}`}>
          {health === null ? 'Connecting…'
            : health.status === 'ok' ? `● ${health.documents.toLocaleString()} documents · ${health.llm}`
            : `● Backend unavailable`}
        </div>
        <h2>Try asking</h2>
        <ul className="examples">
          {examples.map((q) => (
            <li key={q}><button dir="auto" onClick={() => ask(q)} disabled={loading}>{q}</button></li>
          ))}
        </ul>
        <button className="new-chat" onClick={reset}>+ New conversation</button>
      </aside>

      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <h2>What would you like to know?</h2>
              <p className="muted">I translate your question into MongoDB queries, run them, and explain the results.
                Follow-up questions keep the context.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role} ${m.error ? 'error' : ''}`}>
              <div className="bubble" dir="auto">
                {m.role === 'assistant'
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  : m.content}
              </div>
              {m.chart && <ChartView chart={m.chart} rows={m.chartRows} />}
              {m.steps && <Trace steps={m.steps} />}
            </div>
          ))}
          {loading && <div className="msg assistant"><div className="bubble thinking">Analyzing data<span>…</span></div></div>}
          <div ref={endRef} />
        </div>

        <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
          <input dir="auto" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. Which department spent the most on IT goods in 2014?" disabled={loading} />
          <button type="submit" disabled={loading || !input.trim()}>Send</button>
        </form>
      </main>
    </div>
  )
}
