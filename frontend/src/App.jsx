import { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import { API_BASE_URL, createExportJob, getJobs } from './api/jobs'
import './App.css'

const STATUS_LABEL = {
  PENDING: '대기 중',
  PROCESSING: '생성 중',
  DONE: '완료',
  FAILED: '실패',
}

function formatDate(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatDuration(value) {
  if (value == null) return '-'
  return value < 60 ? `${value.toFixed(1)}초` : `${Math.floor(value / 60)}분 ${Math.round(value % 60)}초`
}

function Progress({ job }) {
  if (job.status === 'FAILED') return <span className="error-text">{job.error_message || '알 수 없는 오류'}</span>
  if (job.status === 'PENDING') return <span className="muted">작업 시작을 기다리고 있습니다.</span>

  return (
    <div className="progress-cell">
      <div className="progress-meta">
        <span>{job.progress}%</span>
        <span>{job.processed_rows.toLocaleString()} / {job.total_rows.toLocaleString()}행</span>
      </div>
      <div className="progress-track" aria-label={`진행률 ${job.progress}%`}>
        <span style={{ width: `${job.progress}%` }} />
      </div>
    </div>
  )
}

function DownloadLink({ job }) {
  if (job.status !== 'DONE') return <span className="muted">-</span>

  const url = job.download_url || job.gcs_url
  const downloadable = url?.startsWith('http://') || url?.startsWith('https://')

  return downloadable ? (
    <a className="download-link" href={url} target="_blank" rel="noreferrer">다운로드</a>
  ) : (
    <span className="muted" title="백엔드에서 HTTP 다운로드 URL을 제공해야 합니다.">준비 필요</span>
  )
}

function App() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const requestIdRef = useRef(0)
  const fetchingRef = useRef(false)

  const loadJobs = useCallback(async ({ silent = false } = {}) => {
  if (fetchingRef.current) {
    return
  }

  fetchingRef.current = true
  const requestId = ++requestIdRef.current

  if (!silent) {
    setLoading(true)
  }

  try {
    const data = await getJobs()

    if (requestId !== requestIdRef.current) {
      return
    }

    setJobs(data)
    setError('')
  } catch (requestError) {
    if (requestId === requestIdRef.current) {
      setError(requestError.message)
    }
  } finally {
    fetchingRef.current = false

    if (!silent && requestId === requestIdRef.current) {
      setLoading(false)
    }
  }
}, [])


  useEffect(() => {
    let active = true

    getJobs()
      .then((data) => {
        if (!active) return
        setJobs(data)
        setError('')
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE_URL}/jobs/events`)

    eventSource.addEventListener('job', (event) => {
      const updatedJob = JSON.parse(event.data)

      setJobs((previousJobs) => {
        const exists = previousJobs.some((job) => job.job_id === updatedJob.job_id)
        if (!exists) return [updatedJob, ...previousJobs]

        return previousJobs.map((job) =>
          job.job_id === updatedJob.job_id
            ? { ...job, ...updatedJob }
            : job
        )
      })
    })

    eventSource.onopen = () => {
      loadJobs({ silent: true })
    }

    return () => eventSource.close()
  }, [loadJobs])


  const summary = useMemo(() => ({
    total: jobs.length,
    active: jobs.filter(({ status }) => status === 'PENDING' || status === 'PROCESSING').length,
    done: jobs.filter(({ status }) => status === 'DONE').length,
    failed: jobs.filter(({ status }) => status === 'FAILED').length,
  }), [jobs])

  async function handleCreate() {
    setError('')
    try {
      await createExportJob()
      await loadJobs({ silent: true })
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <main className="page-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">ORDER EXPORT</p>
          <h1>주문 엑셀 내보내기</h1>
          <p className="description">주문 데이터를 엑셀 파일로 생성하고 진행 상태를 확인합니다.</p>
        </div>
        <button className="primary-button" onClick={handleCreate}>
          새 엑셀 만들기
        </button>
      </header>

      {error && <div className="alert" role="alert">{error} <button onClick={() => loadJobs()}>다시 시도</button></div>}

      <section className="summary-grid" aria-label="작업 요약">
        <article><span>전체 작업</span><strong>{summary.total}</strong></article>
        <article><span>진행 중</span><strong>{summary.active}</strong></article>
        <article><span>완료</span><strong>{summary.done}</strong></article>
        <article><span>실패</span><strong>{summary.failed}</strong></article>
      </section>

      <section className="jobs-panel">
        <div className="panel-heading">
          <div><h2>생성 기록</h2><p>진행 중인 작업은 2초마다 자동으로 갱신됩니다.</p></div>
          <button className="text-button" onClick={() => loadJobs()} disabled={loading}>새로고침</button>
        </div>

        {loading ? (
          <div className="empty-state">작업 목록을 불러오는 중입니다…</div>
        ) : jobs.length === 0 ? (
          <div className="empty-state"><strong>아직 생성 기록이 없습니다.</strong><span>첫 번째 주문 엑셀을 만들어보세요.</span></div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>작업</th><th>상태</th><th>진행 상황</th><th>요청 시각</th><th>소요 시간</th><th>파일</th></tr></thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td className="job-id">#{job.job_id}</td>
                    <td><span className={`status status-${job.status.toLowerCase()}`}>{STATUS_LABEL[job.status] || job.status}</span></td>
                    <td><Progress job={job} /></td>
                    <td>{formatDate(job.requested_at)}</td>
                    <td>{formatDuration(job.duration_seconds)}</td>
                    <td><DownloadLink job={job} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
