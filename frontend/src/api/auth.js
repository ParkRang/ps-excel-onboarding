import { clearToken, getToken, request, setToken } from './client'

export { getToken, clearToken }

export function register(email, password) {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function login(email, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setToken(data.access_token)
  return data
}

export function getMe() {
  return request('/auth/me')
}

export function logout() {
  clearToken()
}
