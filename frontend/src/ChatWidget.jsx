import { useEffect, useRef, useState } from 'react'
import {
  Bot, Send, Plus, MessageSquare, X, Sparkles, LogOut,
  Shield, Maximize2, Minimize2, ChevronDown, Clock, Laptop
} from 'lucide-react'
import api from './api'
import { useAuth } from './auth'
import logo from './assets/logo.png'

const suggestions = [
  'Suggest a laptop under ₹60,000 with 16GB RAM',
  'I need a lightweight laptop with good battery',
  'Show me Dell laptops',
  'What is your return policy?'
]

function ComparisonTable({ data }) {
  if (!data || !data.columns || !data.rows) return null
  return (
    <div className="compare-wrap">
      <table className="compare">
        <thead>
          <tr>
            <th />
            {data.columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.label}>
              <td className="row-label">{r.label}</td>
              {r.values.map((v, i) => (
                <td key={i}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ChatWidget({
  isOpen = false,
  onToggle,
  onOpenAdmin,
  externalPrompt,
  onClearExternalPrompt
}) {
  const { user } = useAuth()
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [isExpanded, setIsExpanded] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  const loadConversations = async () => {
    try {
      const { data } = await api.get('/conversations')
      setConversations(data)
    } catch (err) {
      if (err.response?.status !== 401) {
        setError('Cannot reach the backend. Check that FastAPI is running.')
      }
    }
  }

  useEffect(() => {
    loadConversations()
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy, isOpen])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 250)
    }
  }, [isOpen])

  // React to external prompts (e.g., from product cards or comparison tray)
  useEffect(() => {
    if (externalPrompt) {
      if (!isOpen && onToggle) {
        onToggle(true)
      }
      send(externalPrompt)
      if (onClearExternalPrompt) {
        onClearExternalPrompt()
      }
    }
  }, [externalPrompt])

  const newChat = () => {
    setConversationId(null)
    setMessages([])
    setInput('')
    setError('')
    setShowHistory(false)
  }

  const openConversation = async (id) => {
    setConversationId(id)
    setError('')
    setShowHistory(false)
    try {
      const { data } = await api.get(`/conversations/${id}/messages`)
      setMessages(
        data.map((m) => ({
          role: m.sender_type === 'USER' ? 'user' : 'assistant',
          content: m.message_content,
          products: m.payload?.products || [],
          comparison: m.payload?.comparison || null,
        }))
      )
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
        conversation_id: conversationId,
      })
      setConversationId(data.conversation_id)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          products: data.products || [],
          comparison: data.comparison || null,
          intent: data.intent,
        },
      ])
      loadConversations()
    } catch (err) {
      if (err.response?.status === 401) return
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            err.response?.data?.detail ||
            'Something went wrong. Please check backend connection and try again.',
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="chat-widget-root">
      {/* 1. Small Area / Launcher Button when closed */}
      {!isOpen && (
        <div className="chat-launcher-wrap">
          <div className="chat-launcher-bubble" onClick={() => onToggle && onToggle(true)}>
            <Sparkles size={13} className="sparkle-anim" />
            <span>Need advice? Ask VoltKart AI</span>
          </div>
          <button
            className="chat-launcher-btn"
            onClick={() => onToggle && onToggle(true)}
            aria-label="Open AI Shopping Assistant"
            title="Open VoltKart AI Assistant"
          >
            <span className="launcher-pulse" />
            <img src={logo} alt="VoltKart AI" className="launcher-logo" />
            <span className="launcher-badge">AI</span>
          </button>
        </div>
      )}

      {/* 2. Small Chat Window when opened */}
      {isOpen && (
        <div
          className={`small-chat-window ${isExpanded ? 'expanded' : ''}`}
          role="dialog"
          aria-label="VoltKart Shopping Assistant"
        >
          {/* Header */}
          <div className="small-chat-header">
            <div className="chat-header-identity">
              <div className="assistant-avatar">
                <img src={logo} alt="VoltKart AI" height={22} width={22} />
                <span className="online-indicator" />
              </div>
              <div className="assistant-titles">
                <div className="header-main-title">
                  <strong>VoltKart AI</strong>
                  <span className="header-chip">Shopping Pro</span>
                </div>
                <span className="header-status-text">Online • Verified catalog</span>
              </div>
            </div>

            <div className="small-chat-controls">
              <button
                className={`control-btn ${showHistory ? 'active' : ''}`}
                onClick={() => setShowHistory((v) => !v)}
                title="Recent Conversations"
                aria-label="Recent Conversations"
              >
                <Clock size={16} />
              </button>

              <button
                className="control-btn"
                onClick={newChat}
                title="New Conversation"
                aria-label="New Conversation"
              >
                <Plus size={16} />
              </button>

              <button
                className="control-btn"
                onClick={() => setIsExpanded((v) => !v)}
                title={isExpanded ? 'Compact View' : 'Expand View'}
                aria-label="Toggle Expand"
              >
                {isExpanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
              </button>

              <button
                className="control-btn close-widget"
                onClick={() => onToggle && onToggle(false)}
                title="Minimize Chat Window"
                aria-label="Close Chat Window"
              >
                <X size={17} />
              </button>
            </div>
          </div>

          {/* History Drawer Overlay (within the small chat window) */}
          {showHistory && (
            <div className="chat-history-overlay">
              <div className="history-header">
                <div className="history-title">
                  <MessageSquare size={15} />
                  <span>Recent Conversations</span>
                </div>
                <button
                  className="history-new-btn"
                  onClick={newChat}
                >
                  <Plus size={13} /> New Chat
                </button>
              </div>

              <div className="history-list">
                {conversations.length === 0 ? (
                  <p className="no-chats">No past conversations recorded yet.</p>
                ) : (
                  conversations.map((c) => (
                    <button
                      key={c.conversation_id}
                      className={`history-item ${conversationId === c.conversation_id ? 'selected' : ''}`}
                      onClick={() => openConversation(c.conversation_id)}
                    >
                      <MessageSquare size={14} />
                      <span className="history-text">{c.title || 'Conversation'}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Messages Body */}
          <div className="small-chat-body">
            {messages.length === 0 ? (
              <div className="widget-welcome">
                <div className="widget-welcome-icon">
                  <Bot size={28} />
                </div>
                <h3>Your Personal Laptop Shopper</h3>
                <p>
                  Ask me about specs, budgets, comparisons or store policies. I check the real
                  VoltKart catalog to find the exact match for you.
                </p>

                <div className="widget-suggestions">
                  <span className="suggestion-label">Suggested questions:</span>
                  {suggestions.map((s, idx) => (
                    <button
                      key={s}
                      className="suggestion-chip"
                      onClick={() => send(s)}
                    >
                      <span>{s}</span>
                      <span className="arrow">↗</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="widget-messages">
                {messages.map((m, i) => (
                  <div className={`widget-msg-row ${m.role}`} key={i}>
                    <div className="widget-msg-avatar">
                      {m.role === 'user' ? 'You' : <Bot size={15} />}
                    </div>

                    <div className="widget-msg-wrap">
                      <div className="widget-msg-author">
                        {m.role === 'user' ? 'YOU' : 'VOLTKART AI'}
                      </div>
                      <div className="widget-bubble">{m.content}</div>

                      {/* Side-by-side comparison matrix */}
                      {m.comparison && <ComparisonTable data={m.comparison} />}

                      {/* Product recommendation cards */}
                      {!m.comparison && m.products?.length > 0 && (
                        <div className="widget-product-list">
                          {m.products.map((p, idx) => {
                            const ramVal = p.ram_gb || p.ram
                            const storageVal = p.storage_gb || p.storage
                            const weightVal = p.weight_kg || p.weight
                            const batteryVal = p.battery_life_hours || p.battery_life
                            const priceNum = Number(p.price_inr || p.price || 0)

                            return (
                              <article className="widget-product-card" key={p.product_id || idx}>
                                <div className="widget-card-top">
                                  <span className="widget-brand">{p.brand}</span>
                                  <span className="widget-price">₹{priceNum.toLocaleString('en-IN')}</span>
                                </div>
                                <h4 className="widget-product-title">{p.product_name}</h4>
                                <p className="widget-processor">{p.processor}</p>
                                <div className="widget-specs">
                                  <span>{ramVal}GB RAM</span>
                                  <span>{Number(storageVal) >= 1000 ? `${Number(storageVal) / 1000}TB` : `${storageVal}GB`} SSD</span>
                                  {weightVal && <span>{weightVal}kg</span>}
                                  {batteryVal && <span>{batteryVal}h bat</span>}
                                </div>
                              </article>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {busy && (
                  <div className="widget-typing">
                    <span />
                    <span />
                    <span />
                    <em>Analyzing catalog & specs…</em>
                  </div>
                )}

                <div ref={endRef} />
              </div>
            )}

            {error && <div className="widget-error-banner">{error}</div>}
          </div>

          {/* Footer Composer */}
          <div className="small-chat-footer">
            {onOpenAdmin && user?.role === 'ADMIN' && (
              <div className="widget-admin-bar">
                <Shield size={12} />
                <span>Admin permissions active.</span>
                <button className="link-btn" onClick={onOpenAdmin}>
                  Open Admin Panel
                </button>
              </div>
            )}

            <form
              className="widget-composer"
              onSubmit={(e) => {
                e.preventDefault()
                send()
              }}
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about laptops, recommendations, policies…"
                disabled={busy}
              />
              <button
                type="submit"
                disabled={!input.trim() || busy}
                aria-label="Send message"
              >
                <Send size={15} />
              </button>
            </form>
            <p className="widget-disclaimer">
              Powered by VoltKart AI with verified catalog specs.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
