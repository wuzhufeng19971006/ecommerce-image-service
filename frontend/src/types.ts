export type WorkflowId = 'try_on' | 'white_bg' | 'scene' | 'detail' | 'five_shots'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'
export type InputRole = 'garment' | 'model' | 'approved' | 'reference' | 'edit_target'
export type SizeOption = '1024x1024' | '1024x1536' | '1536x1024'
export type QualityOption = 'auto' | 'low' | 'medium' | 'high'

export interface JobOptions {
  style?: string | null
  gender: 'female' | 'male'
  shot: 'full_body' | 'half_body'
  pose: 'natural' | 'editorial'
  side: 'front' | 'back'
  size: SizeOption
  quality: QualityOption
}

export interface Asset {
  id: string
  kind: 'upload' | 'output'
  url: string
  thumb_url: string | null
  download_url: string
  original_name: string
  mime_type: string
  width: number
  height: number
  size_bytes: number
  created_at: string
}

export interface JobInput {
  role: InputRole
  asset: Asset
}

export interface JobError {
  code: string
  message: string
}

export interface Job {
  id: string
  workflow: WorkflowId
  status: JobStatus
  instruction: string
  final_prompt: string
  model: string
  options: JobOptions
  size: SizeOption
  quality: QualityOption
  inputs: JobInput[]
  outputs: Asset[]
  error: JobError | null
  usage: Record<string, unknown> | null
  duration_ms: number | null
  parent_job_id: string | null
  shots_total: number
  shots_done: number
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface GalleryItem {
  job_id: string
  workflow: WorkflowId
  created_at: string
  instruction: string
  final_prompt: string
  options: JobOptions
  output: Asset
}

export interface StyleOption {
  id: string
  label: string
  description: string
}

export interface InputMeta {
  role: InputRole
  label: string
  required: boolean
  hint: string
}

export interface ShotPlanItem {
  id: string
  order: number
  name: string
  purpose: string
}

export interface WorkflowMeta {
  id: WorkflowId
  label: string
  description: string
  inputs: InputMeta[]
  styles: StyleOption[]
  defaults: Partial<JobOptions>
  instruction_hints: string[]
  max_reference_images: number
  shot_plan?: ShotPlanItem[]
}

export interface Option {
  value: string
  label: string
}

export interface Meta {
  workflows: WorkflowMeta[]
  sizes: Option[]
  qualities: Option[]
  max_reference_images: number
  mock: boolean
  configured: boolean
  model: string
}

export interface AppConfig {
  app_name: string
  version: string
  model: string
  api_base: string
  configured: boolean
  mock: boolean
  max_reference_images: number
}

export interface CreateJobPayload {
  workflow: WorkflowId
  inputs: Array<{ asset_id: string; role: InputRole }>
  options: JobOptions
  instruction: string
}

export interface RevisionPayload {
  feedback: string
  output_id?: string
  size?: SizeOption
  quality?: QualityOption
}
