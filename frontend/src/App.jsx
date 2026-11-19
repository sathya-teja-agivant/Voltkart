import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './auth'
import Login from './Login'
import Chat from './Chat'
import Admin from './Admin'

function Shell() {
  const { user, loading } = useAuth()
  const [view, setView] = useState('admin')

  // Admins land on the admin panel after every login.
  useEffect(() => { setView('admin') }, [user?.user_id])

  if (loading) return <div className="splash">Loading…</div>
  if (!user) return <Login />
  if (user.role === 'ADMIN' && view === 'admin') return <Admin onOpenChat={() => setView('chat')} />
  return <Chat onOpenAdmin={user.role === 'ADMIN' ? () => setView('admin') : null} />
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}