import { useEffect, useRef, useState } from 'react'
import { Bot, Laptop, Send, Plus, MessageSquare, Menu, X, Sparkles, LogOut, Shield } from 'lucide-react'
import api from './api'
import { useAuth } from './auth'

const suggestions = [
  'Suggest a laptop under ₹60,000 with 16GB RAM',
  'I need a lightweight laptop with good battery',
  'Show me Dell laptops',
  'What is your return policy?'
]

function ComparisonTable({ data }) {
  return (
    <div className="compare-wrap">
      <table className="compare">
        <thead>
          <tr><th />{data.columns.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.label}>
              <td className="row-label">{r.label}</td>
              {r.values.map((v, i) => <td key={i}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Chat({ onOpenAdmin }) {
  const { user, logout } = useAuth()
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const endRef = useRef(null)

  const loadConversations = async () => {
    try {
      const { data } = await api.get('/conversations')
      setConversations(data)
    } catch (err) {
      if (err.response?.status !== 401) {
        setError('Cannot reach the backend. Start FastAPI and check your API URL.')
      }
    }
  }

  useEffect(() => { loadConversations() }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])

  const newChat = () => {
    setConversationId(null)
    setMessages([])
    setInput('')
    setError('')
  }

  const openConversation = async (id) => {
    setConversationId(id)
    setError('')
    try {
      const { data } = await api.get(`/conversations/${id}/messages`)
      setMessages(data.map((m) => ({
        role: m.sender_type === 'USER' ? 'user' : 'assistant',
        content: m.message_content,
        products: m.payload?.products || [],
        comparison: m.payload?.comparison || null
      })))
    } catch {
      setError('Unable to load this conversation.')
    }
  }

  const send = async (text = input) => {
    const value = text.trim()
    if (!value || busy) return
    setInput('')
    setError('')
    setMessages((prev) => [...prev, { role: 'user', content: value }])
    setBusy(true)
    try {
      const { data } = await api.post('/chat/message', {
        message: value,
        conversation_id: conversationId
      })
      setConversationId(data.conversation_id)
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: data.answer,
        products: data.products || [],
        comparison: data.comparison || null,
        intent: data.intent
      }])
      loadConversations()
    } catch (err) {
      if (err.response?.status === 401) return // session expired, the app returns to the login screen
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: err.response?.data?.detail || 'Something went wrong. Please try again.'
      }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? '' : 'closed'}`}>
        <div className="brand"><div className="brand-icon"><Laptop size={21} /></div><span>VoltKart</span></div>
        <button className="new-chat" onClick={newChat}><Plus size={17} /> New conversation</button>
        <div className="side-label">RECENT CHATS</div>
        <div className="conversation-list">
          {conversations.map((c) => (
            <button key={c.conversation_id}
              className={`conversation ${conversationId === c.conversation_id ? 'selected' : ''}`}
              onClick={() => openConversation(c.conversation_id)}>
              <MessageSquare size={16} /><span>{c.title}</span>
            </button>
          ))}
        </div>
        <div className="user-box">
          <div className="user-info">
            <strong>{user.full_name}</strong>
            <span>{user.email}</span>
          </div>
          <button className="icon-btn light" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="icon-btn" onClick={() => setSidebarOpen((v) => !v)} aria-label="Toggle sidebar">
            {sidebarOpen ? <X size={19} /> : <Menu size={19} />}
          </button>
          <div className="top-title"><span className="status-dot" /> VoltKart Shopping Assistant</div>
          {onOpenAdmin && (
            <button className="model-tag clickable" onClick={onOpenAdmin}><Shield size={14} /> Admin panel</button>
          )}
          {!onOpenAdmin && <div className="model-tag"><Sparkles size={14} /> AI Assistant</div>}
        </header>

        <section className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon"><Bot size={32} /></div>
              <p className="eyebrow">YOUR PERSONAL LAPTOP SHOPPER</p>
              <h1>Find the right laptop.<br /><span>Without the guesswork.</span></h1>
              <p className="welcome-copy">Tell me what you need, your budget, and how you plan to use it. I'll find matching laptops from the VoltKart catalog.</p>
              <div className="suggestion-grid">
                {suggestions.map((s) => <button key={s} onClick={() => send(s)}>{s}<span>↗</span></button>)}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((m, i) => (
                <div className={`message-row ${m.role}`} key={i}>
                  <div className="avatar">{m.role === 'user' ? 'You' : <Bot size={18} />}</div>
                  <div className="message-content">
                    <div className="message-label">{m.role === 'user' ? 'YOU' : 'VOLTKART AI'}</div>
                    <div className="bubble">{m.content}</div>
                    {m.comparison && <ComparisonTable data={m.comparison} />}
                    {!m.comparison && m.products?.length > 0 && (
                      <div className="product-results">
                        {m.products.map((p) => (
                          <article className="product-card" key={p.product_id}>
                            <div className="product-top"><span>{p.brand}</span><span className="price">₹{Number(p.price_inr).toLocaleString('en-IN')}</span></div>
                            <h3>{p.product_name}</h3>
                            <p>{p.processor}</p>
                            <div className="specs">
                              <span>{p.ram_gb}GB RAM</span><span>{p.storage_gb >= 1000 ? `${p.storage_gb / 1000}TB` : `${p.storage_gb}GB`} SSD</span>
                              <span>{p.weight_kg}kg</span><span>{p.battery_life_hours}h battery</span>
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {busy && <div className="typing"><span /><span /><span /> Finding the right information…</div>}
              <div ref={endRef} />
            </div>
          )}
          {error && <div className="error-banner">{error}</div>}
        </section>

        <footer className="composer-wrap">
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about laptops, recommendations or store policies…" disabled={busy} />
            <button type="submit" disabled={!input.trim() || busy} aria-label="Send message"><Send size={18} /></button>
          </form>
          <p className="disclaimer">VoltKart AI uses the store catalog and policies. Always verify important purchase details.</p>
        </footer>
      </main>
    </div>
  )
}