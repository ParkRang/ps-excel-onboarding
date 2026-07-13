import { API_BASE_URL, request } from './client'

// 하위 호환: App.jsx 등에서 './api/jobs'로 API_BASE_URL을 계속 참조한다.
export { API_BASE_URL }

export function getJobs(page = 1, size = 20) {
  return request(`/jobs/page?page=${page}&size=${size}`)
}

export function createExportJob() {
  return request('/create', { method: 'POST' })
}

export function getJobDownloadUrl(jobId) {
  return request(`/jobs/${jobId}/download`)
}
