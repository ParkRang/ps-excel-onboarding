export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

const TOKEN_KEY = 'access_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

// 모든 요청에 Bearer 토큰을 싣고, 401이면 토큰을 지운 뒤 로그아웃 이벤트를 알린다.
export async function request(path, options = {}) {
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })

  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const body = isJson ? await response.json() : null

  if (response.status === 401) {
    clearToken()
    window.dispatchEvent(new Event('auth:logout'))
  }

  if (!response.ok) {
    const detail = body?.detail || body?.message
    throw new Error(detail || `요청에 실패했습니다. (${response.status})`)
  }
  if (!isJson) {
    throw new Error('API가 JSON 대신 다른 형식으로 응답했습니다. 백엔드 주소를 확인해주세요.')
  }
  return body
}
