import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api, { getToken, setToken } from './api'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  // Restore the session on page load.
  useEffect(() => {
    if (!getToken()) return
    api.get('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  // The axios interceptor fires this when the token expires.
  useEffect(() => {
    window.addEventListener('voltkart:logout', logout)
    return () => window.removeEventListener('voltkart:logout', logout)
  }, [logout])

  const authenticate = async (path, body) => {
    const { data } = await api.post(path, body)
    setToken(data.access_token)
    setUser(data.user)
  }

  const login = (email, password) => authenticate('/auth/login', { email, password })
  const register = (full_name, email, password) =>
    authenticate('/auth/register', { full_name, email, password })

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}