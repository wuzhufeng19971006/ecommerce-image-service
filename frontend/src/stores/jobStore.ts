import { defineStore } from 'pinia'
import {
  cancelJob,
  formatApiError,
  getJob,
  listJobs,
  retryJob,
} from '@/api/client'
import type { Job, JobStatus } from '@/types'

const ACTIVE_KEY = 'yitu.activeJobId'
const ACTIVE_STATUSES: JobStatus[] = ['queued', 'running']
let pollTimer: ReturnType<typeof setTimeout> | null = null

function isActive(status: JobStatus): boolean {
  return ACTIVE_STATUSES.includes(status)
}

export const useJobStore = defineStore('job', {
  state: () => ({
    activeJob: null as Job | null,
    recentJobs: [] as Job[],
    recentLoading: false,
    error: '',
  }),
  getters: {
    isWorking: (state) =>
      Boolean(state.activeJob && isActive(state.activeJob.status)),
    activeStatus: (state): JobStatus | null => state.activeJob?.status || null,
    recentResults: (state) =>
      state.recentJobs.filter((job) => job.outputs.length > 0),
  },
  actions: {
    async resume() {
      const jobId = localStorage.getItem(ACTIVE_KEY)
      if (!jobId) return
      try {
        const job = await getJob(jobId)
        this.activeJob = job
        if (isActive(job.status)) {
          this.schedulePoll(1000)
        } else {
          localStorage.removeItem(ACTIVE_KEY)
        }
      } catch {
        localStorage.removeItem(ACTIVE_KEY)
      }
    },
    adopt(job: Job) {
      this.stopPoll()
      this.activeJob = job
      this.error = ''
      localStorage.setItem(ACTIVE_KEY, job.id)
      if (isActive(job.status)) {
        this.schedulePoll(1000)
      }
    },
    schedulePoll(delay = 1300) {
      this.stopPoll()
      pollTimer = setTimeout(() => {
        void this.poll()
      }, delay)
    },
    stopPoll() {
      if (pollTimer) {
        clearTimeout(pollTimer)
        pollTimer = null
      }
    },
    async poll() {
      if (!this.activeJob) return
      const id = this.activeJob.id
      try {
        const job = await getJob(id)
        this.activeJob = job
        this.error = ''
        if (isActive(job.status)) {
          this.schedulePoll()
        } else {
          this.stopPoll()
          localStorage.removeItem(ACTIVE_KEY)
          if (job.status === 'succeeded') {
            void this.refreshRecent()
          }
        }
      } catch (error) {
        this.error = formatApiError(error)
        this.schedulePoll(2600)
      }
    },
    async refreshRecent() {
      this.recentLoading = true
      try {
        const page = await listJobs({ page: 1, page_size: 8, status: 'succeeded' })
        this.recentJobs = page.items
      } catch {
        // Recent results are non-critical; keep the previous list.
      } finally {
        this.recentLoading = false
      }
    },
    async cancelActive() {
      if (!this.activeJob) return
      try {
        const job = await cancelJob(this.activeJob.id)
        this.activeJob = job
        this.stopPoll()
        localStorage.removeItem(ACTIVE_KEY)
      } catch (error) {
        this.error = formatApiError(error)
        throw error
      }
    },
    async retry(jobId: string): Promise<Job> {
      const job = await retryJob(jobId)
      this.adopt(job)
      return job
    },
    clearActive() {
      this.stopPoll()
      this.activeJob = null
      localStorage.removeItem(ACTIVE_KEY)
    },
  },
})
