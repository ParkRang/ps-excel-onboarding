export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

// 백엔드 API_KEY가 켜져 있으면 X-API-Key 헤더로 전송한다(빌드 타임 주입).
// SPA에 내장되는 값이므로 완전한 비밀은 아니며, 익명 트래픽 차단 용도다.
const API_KEY = import.meta.env.VITE_API_KEY

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    },
    ...options,
  })

  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const body = isJson ? await response.json() : null

  if (!response.ok) {
    const detail = body?.detail || body?.message
    throw new Error(detail || `요청에 실패했습니다. (${response.status})`)
  }

  if (!isJson) {
    throw new Error('API가 JSON 대신 다른 형식으로 응답했습니다. 백엔드 주소를 확인해주세요.')
  }

  return body
}

export function getJobs(page = 1, size = 20) {
  return request(`/jobs/page?page=${page}&size=${size}`)
}

export function createExportJob() {
  return request('/create', { method: 'POST' })
}

export function getJobDownloadUrl(jobId) {
  return request(`/jobs/${jobId}/download`)
}
