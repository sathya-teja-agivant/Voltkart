import axios from 'axios'

const TOKEN_KEY = 'voltkart_token'
export const getToken = () => sessionStorage.getItem(TOKEN_KEY)
export const setToken = (t) =>
  t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY)

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1',
})

// No default Content-Type: axios sets JSON for objects and multipart for FormData.
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || ''
    const isAuthCall = url.startsWith('/auth/login') || url.startsWith('/auth/register')
    if (err.response?.status === 401 && !isAuthCall) {
      setToken(null)
      window.dispatchEvent(new Event('voltkart:logout'))
    }
    return Promise.reject(err)
  }
)

export function errorMessage(err, fallback = 'Something went wrong.') {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  return fallback
}

export default api