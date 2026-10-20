import axios, { AxiosError, type AxiosProgressEvent } from 'axios'
import type {
  AppConfig,
  Asset,
  CreateJobPayload,
  GalleryItem,
  Job,
  Meta,
  Page,
  RevisionPayload,
} from '@/types'

export class ApiError extends Error {
  code: string
  status: number

  constructor(message: string, code = 'UNKNOWN', status = 0) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

const http = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new ApiError('请求超时，请稍后重试', 'CLIENT_TIMEOUT', 0))
    }
    if (!error.response) {
      return Promise.reject(
        new ApiError('无法连接后端服务，请确认服务已启动', 'NETWORK_ERROR', 0),
      )
    }
    const data = error.response.data as
      | { error?: { code?: string; message?: string } }
      | undefined
    const message = data?.error?.message || error.message || '请求失败'
    return Promise.reject(
      new ApiError(message, data?.error?.code || 'HTTP_ERROR', error.response.status),
    )
  },
)

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return '操作失败，请稍后重试'
}

export async function fetchConfig(): Promise<AppConfig> {
  const { data } = await http.get<AppConfig>('/config')
  return data
}

export async function fetchMeta(): Promise<Meta> {
  const { data } = await http.get<Meta>('/meta')
  return data
}

export async function uploadAsset(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Asset> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<Asset>('/assets', form, {
    timeout: 120_000,
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

export async function deleteAsset(assetId: string): Promise<void> {
  await http.delete(`/assets/${assetId}`)
}

export async function createJob(payload: CreateJobPayload): Promise<Job> {
  const { data } = await http.post<Job>('/jobs', payload, { timeout: 60_000 })
  return data
}

export async function getJob(jobId: string): Promise<Job> {
  const { data } = await http.get<Job>(`/jobs/${jobId}`)
  return data
}

export async function listJobs(params: {
  page?: number
  page_size?: number
  status?: string
  workflow?: string
}): Promise<Page<Job>> {
  const { data } = await http.get<Page<Job>>('/jobs', { params })
  return data
}

export async function cancelJob(jobId: string): Promise<Job> {
  const { data } = await http.post<Job>(`/jobs/${jobId}/cancel`)
  return data
}

export async function retryJob(jobId: string): Promise<Job> {
  const { data } = await http.post<Job>(`/jobs/${jobId}/retry`)
  return data
}

export async function reviseJob(
  jobId: string,
  payload: RevisionPayload,
): Promise<Job> {
  const { data } = await http.post<Job>(`/jobs/${jobId}/revise`, payload, {
    timeout: 60_000,
  })
  return data
}

export async function fetchGallery(params: {
  page?: number
  page_size?: number
  workflow?: string
}): Promise<Page<GalleryItem>> {
  const { data } = await http.get<Page<GalleryItem>>('/gallery', { params })
  return data
}
