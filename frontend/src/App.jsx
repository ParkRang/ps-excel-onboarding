import { useCallback, useEffect, useState, useRef } from 'react'
import { API_BASE_URL, createExportJob, getJobDownloadUrl, getJobs } from './api/jobs'
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
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')

  if (job.status !== 'DONE') return <span className="muted">-</span>

  async function handleDownload() {
    setDownloading(true)
    setDownloadError('')
    try {
      const { download_url: downloadUrl } = await getJobDownloadUrl(job.job_id)
      const targetUrl = downloadUrl.startsWith('http')
        ? downloadUrl
        : `${API_BASE_URL}${downloadUrl}`
      window.location.assign(targetUrl)
    } catch (error) {
      setDownloadError(error.message)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <button
      type="button"
      className="download-link"
      onClick={handleDownload}
      disabled={downloading}
      title={downloadError}
    >
      {downloading ? 'URL 생성 중…' : downloadError ? '다시 시도' : '다운로드'}
    </button>
  )
}

const PAGE_SIZE = 20

function App() {
  const [jobs, setJobs] = useState([])
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [summary, setSummary] = useState({ total: 0, active: 0, done: 0, failed: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [requestingCount, setRequestingCount] = useState(0)

  const requestIdRef = useRef(0)
  const jobsRef = useRef([])
  const pageRef = useRef(1)

  useEffect(() => {
    jobsRef.current = jobs
  }, [jobs])

  useEffect(() => {
    pageRef.current = page
  }, [page])

  const loadJobs = useCallback(async ({ targetPage = pageRef.current } = {}) => {
    const requestId = ++requestIdRef.current

    try {
      const data = await getJobs(targetPage, PAGE_SIZE)
      if (requestId !== requestIdRef.current) return

      setJobs(data.items)
      setPage(data.page)
      setPages(data.pages)
      setSummary({
        total: data.total,
        active: data.active,
        done: data.done,
        failed: data.failed,
      })
      setError('')
    } catch (requestError) {
      if (requestId === requestIdRef.current) setError(requestError.message)
    }
  }, [])

  useEffect(() => {
    let active = true
    getJobs(1, PAGE_SIZE)
      .then((data) => {
        if (!active) return
        setJobs(data.items)
        setPages(data.pages)
        setSummary({
          total: data.total,
          active: data.active,
          done: data.done,
          failed: data.failed,
        })
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
    // ===== [ADD] 진짜 SSE 연결 =====
    // 브라우저가 GET /jobs/events 요청을 열어둠.
    // 서버가 이벤트를 보내면 addEventListener("job")이 즉시 실행됨.
    const eventSource = new EventSource(`${API_BASE_URL}/jobs/events`)

    eventSource.onopen = () => {
      // ===== [ADD] 연결 직후 현재 목록 한번 동기화 =====
      loadJobs({ targetPage: pageRef.current })
    }

    eventSource.addEventListener("job", (event) => {
      // ===== [ADD] 서버에서 push한 job 상태 수신 =====
      const updatedJob = JSON.parse(event.data)

      setJobs((currentJobs) => {
        const exists = currentJobs.some(
          (job) => job.job_id === updatedJob.job_id
        )

        if (exists) {
          return currentJobs.map((job) =>
            job.job_id === updatedJob.job_id
              ? { ...job, ...updatedJob }
              : job
          )
        }

        if (pageRef.current === 1 && updatedJob.status === 'PENDING') {
          return [updatedJob, ...currentJobs].slice(0, PAGE_SIZE)
        }

        return currentJobs
      })

      const previousJob = jobsRef.current.find(
        (job) => job.job_id === updatedJob.job_id
      )

      if (previousJob && previousJob.status !== updatedJob.status) {
        loadJobs({ targetPage: pageRef.current })
      }
    })

    eventSource.onerror = (error) => {
      // ===== [IMPORTANT]
      // 여기서 close() 하지 않으면 브라우저 EventSource가 자동 재연결 시도함.
      console.error("SSE connection error", error)
    }

    return () => {
      // ===== [ADD] 컴포넌트 unmount 시 SSE 연결 종료 =====
      eventSource.close()
    }
  }, [loadJobs])


  // useEffect(() => {
  //   const eventSource = new EventSource(`${API_BASE_URL}/jobs/events`)

  //   eventSource.addEventListener('job', (event) => {
  //     const updatedJob = JSON.parse(event.data)
  //     const previousJob = jobsRef.current.find((job) => job.job_id === updatedJob.job_id)

  //     setJobs((previousJobs) => {
  //       const exists = previousJobs.some((job) => job.job_id === updatedJob.job_id)
  //       if (!exists) {
  //         return pageRef.current === 1 && updatedJob.status === 'PENDING'
  //           ? [updatedJob, ...previousJobs].slice(0, PAGE_SIZE)
  //           : previousJobs
  //       }

  //       return previousJobs.map((job) =>
  //         job.job_id === updatedJob.job_id ? { ...job, ...updatedJob } : job
  //       )
  //     })

  //     if (!previousJob || previousJob.status !== updatedJob.status) {
  //       loadJobs({ targetPage: pageRef.current })
  //     }
  //   })

  //   eventSource.onopen = () => loadJobs({ targetPage: pageRef.current })
  //   return () => eventSource.close()
  // }, [loadJobs])

  async function handleCreate() {
    setError('')
    setRequestingCount((count) => count + 1)

    try {
      await createExportJob()
      setPage(1)
      await loadJobs({ targetPage: 1 })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRequestingCount((count) => Math.max(0, count - 1))
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
        <div className="create-actions">
          {requestingCount > 0 && (
            <span className="request-indicator">요청 전송 중 {requestingCount}건</span>
          )}
          <button className="primary-button" onClick={handleCreate}>
            새 엑셀 만들기
          </button>
        </div>
      </header>

      {error && <div className="alert" role="alert">{error} <button onClick={() => loadJobs({ targetPage: page })}>다시 시도</button></div>}

      <section className="summary-grid" aria-label="작업 요약">
        <article><span>전체 작업</span><strong>{summary.total}</strong></article>
        <article><span>진행 중</span><strong>{summary.active}</strong></article>
        <article><span>완료</span><strong>{summary.done}</strong></article>
        <article><span>실패</span><strong>{summary.failed}</strong></article>
      </section>

      <section className="jobs-panel">
        <div className="panel-heading">
          <div><h2>생성 기록</h2><p>진행 상태는 실시간으로 갱신됩니다.</p></div>
          <button className="text-button" onClick={() => loadJobs({ targetPage: page })}>새로고침</button>
        </div>

        {loading ? (
          <div className="empty-state">작업 목록을 불러오는 중입니다…</div>
        ) : jobs.length === 0 ? (
          <div className="empty-state"><strong>아직 생성 기록이 없습니다.</strong><span>첫 번째 주문 엑셀을 만들어보세요.</span></div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead><tr><th>작업</th><th>상태</th><th>진행 상황</th><th>요청 시각</th><th>완료 시각</th><th>소요 시간</th><th>파일</th></tr></thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.job_id}>
                      <td className="job-id">#{job.job_id}</td>
                      <td><span className={`status status-${job.status.toLowerCase()}`}>{STATUS_LABEL[job.status] || job.status}</span></td>
                      <td><Progress job={job} /></td>
                      <td>{formatDate(job.requested_at)}</td>
                      <td>{formatDate(job.completed_at)}</td>
                      <td>{formatDuration(job.duration_seconds)}</td>
                      <td><DownloadLink job={job} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav className="pagination" aria-label="작업 목록 페이지">
              <button
                type="button"
                onClick={() => {
                  const targetPage = Math.max(1, page - 1)
                  setPage(targetPage)
                  loadJobs({ targetPage })
                }}
                disabled={page <= 1}
              >
                이전
              </button>
              <span>{page} / {pages} 페이지 · 총 {summary.total.toLocaleString()}건</span>
              <button
                type="button"
                onClick={() => {
                  const targetPage = Math.min(pages, page + 1)
                  setPage(targetPage)
                  loadJobs({ targetPage })
                }}
                disabled={page >= pages}
              >
                다음
              </button>
            </nav>
          </>
        )}
      </section>
    </main>
  )
}

export default App
