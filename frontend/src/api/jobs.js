const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json()
      detail = body.detail || body.message || ''
    } catch {
      // JSON이 아닌 오류 응답은 상태 코드만 사용합니다.
    }
    throw new Error(detail || `요청에 실패했습니다. (${response.status})`)
  }

  return response.json()
}

export function getJobs() {
  return request('/jobs')
}

export function createExportJob() {
  return request('/create', { method: 'POST' })
}
