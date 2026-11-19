import { useState } from 'react'
import { AuthProvider, useAuth } from './auth'
import Login from './Login'
import Admin from './Admin'
import ProductsPage from './ProductsPage'
import ChatWidget from './ChatWidget'

function Shell() {
  const { user, loading } = useAuth()
  const [view, setView] = useState('store') // Default view is the e-commerce store
  const [chatOpen, setChatOpen] = useState(false) // Floating assistant closed by default as a small area launcher
  const [externalPrompt, setExternalPrompt] = useState(null)

  const handleOpenChat = (prompt) => {
    setChatOpen(true)
    if (prompt) {
      setExternalPrompt(prompt)
    }
  }

  if (loading) return <div className="splash">Loading…</div>
  if (!user) return <Login />

  return (
    <div className="saas-app-shell">
      {view === 'admin' && user.role === 'ADMIN' ? (
        <Admin
          onOpenChat={() => handleOpenChat()}
          onOpenStore={() => setView('store')}
        />
      ) : (
        <ProductsPage
          onOpenChat={() => handleOpenChat()}
          onOpenAdmin={user.role === 'ADMIN' ? () => setView('admin') : null}
          onAskAboutProduct={(prompt) => handleOpenChat(prompt)}
          onCompareProducts={(prompt) => handleOpenChat(prompt)}
        />
      )}

      {/* Floating Chat Assistant: appears as a small area launcher and expands into a small chat window */}
      <ChatWidget
        isOpen={chatOpen}
        onToggle={(open) => setChatOpen(open)}
        onOpenAdmin={user.role === 'ADMIN' && view !== 'admin' ? () => setView('admin') : null}
        externalPrompt={externalPrompt}
        onClearExternalPrompt={() => setExternalPrompt(null)}
      />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}
