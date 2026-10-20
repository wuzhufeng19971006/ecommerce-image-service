<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  Close,
  CopyDocument,
  Download,
  MagicStick,
  Picture,
  RefreshLeft,
  WarningFilled,
} from '@element-plus/icons-vue'
import {
  createJob,
  formatApiError,
  getJob,
  reviseJob,
  uploadAsset,
} from '@/api/client'
import type {
  Asset,
  CreateJobPayload,
  Job,
  JobOptions,
  WorkflowId,
} from '@/types'
import EmptyStage from '@/components/EmptyStage.vue'
import StylePicker from '@/components/StylePicker.vue'
import UploadSlot from '@/components/UploadSlot.vue'
import WorkflowPicker from '@/components/WorkflowPicker.vue'
import { useAppStore } from '@/stores/appStore'
import { useJobStore } from '@/stores/jobStore'
import {
  STATUS_LABELS,
  WORKFLOW_LABELS,
  copyText,
  formatDate,
  formatDuration,
  formatElapsed,
} from '@/utils/format'

const appStore = useAppStore()
const jobStore = useJobStore()
const route = useRoute()
const router = useRouter()

const workflow = ref<WorkflowId>('try_on')
const garmentAsset = ref<Asset | null>(null)
const modelAsset = ref<Asset | null>(null)
const approvedAsset = ref<Asset | null>(null)
const product2Asset = ref<Asset | null>(null)
const extraAssets = ref<Asset[]>([])
const instruction = ref('')
const formError = ref('')
const submitting = ref(false)
const loadingSampleModel = ref(false)
const previewJob = ref<Job | null>(null)
const promptOpen = ref(false)
const revisionOpen = ref(false)
const revisionFeedback = ref('')
const revising = ref(false)
const selectedOutputIndex = ref(0)
const stageRef = ref<HTMLElement | null>(null)
const pendingReuseId = ref<string | null>(null)
const elapsedSeconds = ref(0)
const uploading = reactive({
  garment: false,
  model: false,
  approved: false,
  product2: false,
  extra: false,
})
const uploadProgress = reactive({
  garment: 0,
  model: 0,
  approved: 0,
  product2: 0,
  extra: 0,
})
let elapsedTimer: ReturnType<typeof setInterval> | null = null
let suppressDefaults = false
let metaInitialized = false

const options = reactive<JobOptions>({
  style: 'studio',
  gender: 'female',
  shot: 'full_body',
  pose: 'natural',
  side: 'front',
  size: '1024x1536',
  quality: 'auto',
})

const metaForWorkflow = computed(() =>
  appStore.meta?.workflows.find((item) => item.id === workflow.value),
)
const styles = computed(() => metaForWorkflow.value?.styles || [])
const isTryOn = computed(() => workflow.value === 'try_on')
const isFiveShots = computed(() => workflow.value === 'five_shots')
const fiveShotPlan = computed(() => metaForWorkflow.value?.shot_plan || [])
const displayJob = computed(() => previewJob.value || jobStore.activeJob)
const isBusy = computed(
  () =>
    displayJob.value?.status === 'queued' || displayJob.value?.status === 'running',
)
const currentOutput = computed(
  () => displayJob.value?.outputs[selectedOutputIndex.value] || displayJob.value?.outputs[0],
)
const recentResults = computed(() => jobStore.recentResults.slice(0, 6))
const workflowLabel = computed(() =>
  displayJob.value ? WORKFLOW_LABELS[displayJob.value.workflow] : '等待创作',
)
const statusText = computed(() =>
  displayJob.value ? STATUS_LABELS[displayJob.value.status] : '',
)
const statusClass = computed(() => {
  const status = displayJob.value?.status
  if (!status) return ''
  if (status === 'failed') return 'is-failed'
  if (status === 'succeeded') return 'is-success'
  if (status === 'canceled') return 'is-canceled'
  return 'is-running'
})
const seriesProgress = computed(() => {
  const job = displayJob.value
  if (!job || job.shots_total <= 1) return 0
  return Math.min(100, Math.round((job.shots_done / job.shots_total) * 100))
})
const extraLimit = computed(() => {
  if (workflow.value === 'white_bg' || workflow.value === 'scene') return 3
  if (workflow.value === 'detail') return 2
  return 2
})
const canAddExtra = computed(
  () => workflow.value !== 'try_on' && extraAssets.value.length < extraLimit.value,
)
const uploadingAny = computed(
  () =>
    uploading.garment ||
    uploading.model ||
    uploading.approved ||
    uploading.product2 ||
    uploading.extra,
)
const canGenerate = computed(
  () =>
    Boolean(appStore.configured) &&
    Boolean(garmentAsset.value) &&
    (!isFiveShots.value || Boolean(product2Asset.value)) &&
    !uploadingAny.value &&
    !submitting.value &&
    !jobStore.isWorking,
)
const disabledReason = computed(() => {
  if (!appStore.configured) return '配置接口密钥后即可开始生成'
  if (!garmentAsset.value) {
    return isFiveShots.value ? '请上传商品图 1' : '请先上传一张服装图'
  }
  if (isFiveShots.value && !product2Asset.value) return '请上传商品图 2'
  if (uploadingAny.value) return '图片上传完成后即可生成'
  if (jobStore.isWorking) return '已有任务正在生成，请等待完成'
  return ''
})
const hints = computed(() => metaForWorkflow.value?.instruction_hints || [])

function applyWorkflowDefaults() {
  const defaults = metaForWorkflow.value?.defaults
  if (!defaults) return
  Object.assign(options, defaults)
}

watch(
  () => workflow.value,
  () => {
    if (!suppressDefaults) applyWorkflowDefaults()
    formError.value = ''
    selectedOutputIndex.value = 0
  },
)

watch(
  () => appStore.meta,
  (meta) => {
    if (!meta) return
    if (!metaInitialized) {
      metaInitialized = true
      applyWorkflowDefaults()
    }
    void loadPendingReuse()
  },
  { immediate: true },
)

async function loadPendingReuse() {
  if (!pendingReuseId.value || !appStore.meta) return
  const id = pendingReuseId.value
  pendingReuseId.value = null
  try {
    const job = await getJob(id)
    await applyJob(job)
    ElMessage.success('已载入这组参数')
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    await router.replace({ path: '/' })
  }
}

watch(
  () => displayJob.value?.id,
  () => {
    selectedOutputIndex.value = 0
  },
)

watch(
  [() => displayJob.value?.id, () => displayJob.value?.status],
  () => syncElapsed(),
  { immediate: true },
)

onMounted(() => {
  if (typeof route.query.reuse === 'string') {
    pendingReuseId.value = route.query.reuse
    void loadPendingReuse()
  }
})

onBeforeUnmount(() => {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
})

function syncElapsed() {
  const job = displayJob.value
  if (job && (job.status === 'queued' || job.status === 'running')) {
    updateElapsed()
    if (!elapsedTimer) {
      elapsedTimer = setInterval(updateElapsed, 1000)
    }
  } else {
    if (elapsedTimer) {
      clearInterval(elapsedTimer)
      elapsedTimer = null
    }
    elapsedSeconds.value = 0
  }
}

function updateElapsed() {
  const job = displayJob.value
  if (!job || (job.status !== 'queued' && job.status !== 'running')) return
  const startValue = job.started_at || job.created_at
  const start = new Date(startValue).getTime()
  if (Number.isNaN(start)) return
  elapsedSeconds.value = Math.max(0, Math.floor((Date.now() - start) / 1000))
}

function isAllowedImage(file: File): boolean {
  const allowed = ['image/jpeg', 'image/png', 'image/webp']
  if (file.type) return allowed.includes(file.type)
  return /\.(jpe?g|png|webp)$/i.test(file.name)
}

const revisionHints = [
  '站姿太僵，改自然一些',
  '手指像展示式张开',
  '皮肤磨皮太重',
  '光线太平，缺少接触阴影',
  '衣服褶皱不自然',
  '保留脸和服装不变',
]

async function handleUpload(
  kind: 'garment' | 'model' | 'approved' | 'product2' | 'extra',
  file: File,
) {
  if (!isAllowedImage(file)) {
    ElMessage.error('仅支持 JPG、PNG、WebP 图片')
    return
  }
  if (file.size > 15 * 1024 * 1024) {
    ElMessage.error('图片不能超过 15 MB')
    return
  }
  if (kind === 'extra' && extraAssets.value.length >= extraLimit.value) {
    ElMessage.warning(`当前模式最多 ${extraLimit.value} 张补充参考图`)
    return
  }
  uploading[kind] = true
  uploadProgress[kind] = 0
  formError.value = ''
  try {
    const asset = await uploadAsset(file, (percent) => {
      uploadProgress[kind] = percent
    })
    if (kind === 'garment') garmentAsset.value = asset
    if (kind === 'model') modelAsset.value = asset
    if (kind === 'approved') approvedAsset.value = asset
    if (kind === 'product2') product2Asset.value = asset
    if (kind === 'extra') extraAssets.value.push(asset)
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    uploading[kind] = false
    uploadProgress[kind] = 0
  }
}

function buildInputs(): CreateJobPayload['inputs'] {
  const inputs: CreateJobPayload['inputs'] = []
  if (garmentAsset.value) {
    inputs.push({ asset_id: garmentAsset.value.id, role: 'garment' })
  }
  if (isFiveShots.value) {
    if (product2Asset.value) {
      inputs.push({ asset_id: product2Asset.value.id, role: 'reference' })
    }
    return inputs
  }
  if (isTryOn.value && modelAsset.value) {
    inputs.push({ asset_id: modelAsset.value.id, role: 'model' })
  }
  if (isTryOn.value && approvedAsset.value) {
    inputs.push({ asset_id: approvedAsset.value.id, role: 'approved' })
  }
  if (!isTryOn.value) {
    for (const asset of extraAssets.value) {
      inputs.push({ asset_id: asset.id, role: 'reference' })
    }
  }
  return inputs
}

async function submit() {
  formError.value = ''
  if (!appStore.configured) {
    formError.value = '尚未配置生图接口，请先配置 .env 并重启后端'
    return
  }
  if (!garmentAsset.value) {
    formError.value = isFiveShots.value ? '请上传商品图 1' : '请先上传一张服装图'
    return
  }
  if (isFiveShots.value && !product2Asset.value) {
    formError.value = '五图套图需要两张同款商品图'
    return
  }
  if (jobStore.isWorking) {
    formError.value = '已有任务正在生成，请等待完成'
    return
  }
  submitting.value = true
  try {
    const job = await createJob({
      workflow: workflow.value,
      inputs: buildInputs(),
      options: { ...options },
      instruction: instruction.value.trim(),
    })
    jobStore.adopt(job)
    previewJob.value = null
    selectedOutputIndex.value = 0
    ElMessage.success('任务已提交，正在生成')
    await nextTick()
    stageRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (error) {
    formError.value = formatApiError(error)
  } finally {
    submitting.value = false
  }
}

async function retryActive() {
  const job = displayJob.value
  if (!job) return
  try {
    await jobStore.retry(job.id)
    previewJob.value = null
    selectedOutputIndex.value = 0
    ElMessage.success('已重新提交生成任务')
  } catch (error) {
    ElMessage.error(formatApiError(error))
  }
}

async function cancelActive() {
  try {
    await jobStore.cancelActive()
    ElMessage.success('已取消排队任务')
  } catch (error) {
    ElMessage.error(formatApiError(error))
  }
}

function openRecent(job: Job) {
  previewJob.value = job
  selectedOutputIndex.value = 0
  void nextTick(() => {
    stageRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function applyJob(job: Job) {
  suppressDefaults = true
  workflow.value = job.workflow
  await nextTick()
  garmentAsset.value = job.inputs.find((item) => item.role === 'garment')?.asset || null
  modelAsset.value = job.inputs.find((item) => item.role === 'model')?.asset || null
  approvedAsset.value = job.inputs.find((item) => item.role === 'approved')?.asset || null
  product2Asset.value =
    job.workflow === 'five_shots'
      ? job.inputs.find((item) => item.role === 'reference')?.asset || null
      : null
  extraAssets.value =
    job.workflow === 'five_shots'
      ? []
      : job.inputs
          .filter((item) => item.role === 'reference')
          .map((item) => item.asset)
  Object.assign(options, job.options)
  instruction.value = job.instruction
  previewJob.value = job
  selectedOutputIndex.value = 0
  suppressDefaults = false
}

async function useCurrentParams() {
  if (!displayJob.value) return
  await applyJob(displayJob.value)
  ElMessage.success('已把这组参数带回创作台')
}

function useHint(hint: string) {
  if (instruction.value.includes(hint)) return
  instruction.value = instruction.value
    ? `${instruction.value.replace(/[，,]$/, '')}，${hint}`
    : hint
}

async function useSampleModel() {
  if (uploading.model) return
  loadingSampleModel.value = true
  try {
    const response = await fetch('/samples/model-triptych.png')
    if (!response.ok) throw new Error('示例模特图加载失败')
    const blob = await response.blob()
    const file = new File([blob], 'model-triptych.png', {
      type: blob.type || 'image/png',
    })
    await handleUpload('model', file)
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    loadingSampleModel.value = false
  }
}

function openRevision() {
  if (!displayJob.value || !currentOutput.value) return
  revisionFeedback.value = ''
  revisionOpen.value = true
}

function useRevisionHint(hint: string) {
  if (revisionFeedback.value.includes(hint)) return
  revisionFeedback.value = revisionFeedback.value
    ? `${revisionFeedback.value.replace(/[，,]$/, '')}，${hint}`
    : hint
}

async function submitRevision() {
  const source = displayJob.value
  const output = currentOutput.value
  if (!source || !output) return
  const feedback = revisionFeedback.value.trim()
  if (!feedback) {
    ElMessage.warning('请描述需要调整的问题')
    return
  }
  revising.value = true
  try {
    const job = await reviseJob(source.id, {
      feedback,
      output_id: output.id,
    })
    jobStore.adopt(job)
    previewJob.value = null
    selectedOutputIndex.value = 0
    revisionOpen.value = false
    ElMessage.success('已提交定向改图，正在重新拍摄')
    await nextTick()
    stageRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    revising.value = false
  }
}

async function copyPrompt() {
  if (!displayJob.value?.final_prompt) return
  try {
    await copyText(displayJob.value.final_prompt)
    ElMessage.success('提示词已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择文本')
  }
}

function removeExtra(index: number) {
  extraAssets.value.splice(index, 1)
}
</script>

<template>
  <section class="studio-page">
    <header class="page-hero">
      <div class="page-hero-copy">
        <span class="eyebrow">AI CLOTHING VISUALS</span>
        <h2>把衣服，<em>穿进画面里。</em></h2>
        <p>
          为服装电商准备的五条视觉路径：真人试穿、白底平铺、场景氛围、细节特写，
          以及两张商品图自动生成五张职责图的套图模式。上传产品图，选择风格，剩下的交给画面。
        </p>
      </div>
      <div class="page-hero-aside">
        <span>01</span>
        <p>Upload<br />Compose<br />Generate</p>
      </div>
    </header>

    <div class="studio-layout">
      <section class="panel composer">
        <div class="panel-head">
          <span class="panel-index">01</span>
          <div>
            <h3>选择创作模式</h3>
            <p>不同模式的提示词与构图策略已分别调校</p>
          </div>
        </div>
        <WorkflowPicker
          v-if="appStore.workflows.length"
          v-model="workflow"
          :workflows="appStore.workflows"
        />
        <div v-else class="skeleton-block"></div>

        <div class="panel-divider"></div>

        <div class="field-block">
          <div class="field-head">
            <label>上传素材</label>
            <span v-if="isFiveShots">两张同款商品图，自动生成五张</span>
            <span v-else>{{ isTryOn ? '服装必填；模特与认可成片可选' : '首张作为服装主体' }}</span>
          </div>

          <template v-if="isFiveShots">
            <div class="upload-row">
              <UploadSlot
                label="商品图 1"
                hint="优先确定主体颜色与款式"
                required
                :asset="garmentAsset"
                :uploading="uploading.garment"
                :progress="uploadProgress.garment"
                @select="handleUpload('garment', $event)"
                @remove="garmentAsset = null"
              />
              <UploadSlot
                label="商品图 2"
                hint="补充比例、角度或局部信息"
                required
                :asset="product2Asset"
                :uploading="uploading.product2"
                :progress="uploadProgress.product2"
                @select="handleUpload('product2', $event)"
                @remove="product2Asset = null"
              />
            </div>
            <p class="series-hint">
              两张必须是同款商品。光线差异不会被当成新颜色，冲突细节不会被拼成第三款商品。
            </p>
          </template>

          <template v-else>
            <div class="upload-row">
              <UploadSlot
                label="服装图"
                hint="实物商品图，决定颜色与细节"
                required
                :asset="garmentAsset"
                :uploading="uploading.garment"
                :progress="uploadProgress.garment"
                @select="handleUpload('garment', $event)"
                @remove="garmentAsset = null"
              />
              <UploadSlot
                v-if="isTryOn"
                label="模特图"
                hint="可选，建议正面/侧面/背面清晰参考"
                :asset="modelAsset"
                :uploading="uploading.model"
                :progress="uploadProgress.model"
                @select="handleUpload('model', $event)"
                @remove="modelAsset = null"
              />
            </div>

            <div v-if="isTryOn" class="assist-row">
              <UploadSlot
                class="approved-slot"
                label="认可成片（可选）"
                hint="统一质感与上身比例"
                compact
                :asset="approvedAsset"
                :uploading="uploading.approved"
                :progress="uploadProgress.approved"
                @select="handleUpload('approved', $event)"
                @remove="approvedAsset = null"
              />
              <div class="assist-copy">
                <button
                  v-if="!modelAsset"
                  type="button"
                  class="sample-model-link"
                  :disabled="loadingSampleModel || uploading.model"
                  @click="useSampleModel"
                >
                  <el-icon><Picture /></el-icon>
                  {{ loadingSampleModel ? '正在载入示例…' : '使用示例三视图模特' }}
                </button>
                <p>
                  三视图只用于锁定身份；模型仍会生成一张独立照片。认可成片用于统一本组的
                  光线、比例与面料垂感。
                </p>
              </div>
            </div>

            <div v-if="!isTryOn" class="extra-upload-block">
              <div class="extra-head">
                <span>补充参考</span>
                <small>{{ extraAssets.length }} / {{ extraLimit }}</small>
              </div>
              <div class="extra-grid">
                <div v-for="(asset, index) in extraAssets" :key="asset.id" class="extra-thumb">
                  <img :src="asset.thumb_url || asset.url" :alt="`补充参考 ${index + 1}`" />
                  <button type="button" aria-label="移除补充参考" @click="removeExtra(index)">
                    <el-icon><Close /></el-icon>
                  </button>
                </div>
                <UploadSlot
                  v-if="canAddExtra"
                  class="extra-add"
                  label="补充参考"
                  hint="背面 / 细节"
                  compact
                  :uploading="uploading.extra"
                  :progress="uploadProgress.extra"
                  @select="handleUpload('extra', $event)"
                />
              </div>
            </div>
          </template>
        </div>

        <div v-if="isFiveShots" class="field-block">
          <div class="field-head">
            <label>五张图职责</label>
            <span>自动编排，不需要逐张写构图</span>
          </div>
          <div class="five-plan-list">
            <div v-for="plan in fiveShotPlan" :key="plan.id" class="five-plan-item">
              <span class="five-plan-order">{{ String(plan.order).padStart(2, '0') }}</span>
              <div>
                <strong>{{ plan.name }}</strong>
                <p>{{ plan.purpose }}</p>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="field-block">
          <div class="field-head">
            <label>画面风格</label>
            <span>{{ metaForWorkflow?.styles.length || 0 }} 种预设</span>
          </div>
          <StylePicker v-model="options.style" :styles="styles" />
        </div>

        <div v-if="isTryOn" class="field-block">
          <div class="field-head">
            <label>镜头与模特</label>
            <span>{{ modelAsset ? '沿用上传模特的姿态' : 'AI 模特描述' }}</span>
          </div>
          <div class="option-row">
            <div class="mini-field">
              <span>镜头</span>
              <el-select v-model="options.shot" size="large">
                <el-option label="全身" value="full_body" />
                <el-option label="半身" value="half_body" />
              </el-select>
            </div>
            <div v-if="!modelAsset" class="mini-field">
              <span>姿态</span>
              <el-select v-model="options.pose" size="large">
                <el-option label="自然站姿" value="natural" />
                <el-option label="杂志姿态" value="editorial" />
              </el-select>
            </div>
          </div>
          <div v-if="!modelAsset" class="segmented-field">
            <span>AI 模特</span>
            <div class="segmented">
              <button
                type="button"
                :class="{ active: options.gender === 'female' }"
                @click="options.gender = 'female'"
              >女模</button>
              <button
                type="button"
                :class="{ active: options.gender === 'male' }"
                @click="options.gender = 'male'"
              >男模</button>
            </div>
          </div>
        </div>

        <div v-if="workflow === 'white_bg'" class="field-block compact-block">
          <div class="field-head">
            <label>展示面</label>
            <span>平铺与人台均适用</span>
          </div>
          <div class="segmented">
            <button
              type="button"
              :class="{ active: options.side === 'front' }"
              @click="options.side = 'front'"
            >正面</button>
            <button
              type="button"
              :class="{ active: options.side === 'back' }"
              @click="options.side = 'back'"
            >背面</button>
          </div>
        </div>

        <details class="advanced-block">
          <summary>
            <span>尺寸、画质与补充要求</span>
            <span class="summary-meta">{{ options.size }} · {{ options.quality }}</span>
          </summary>
          <div class="advanced-body">
            <div class="option-row">
              <div class="mini-field">
                <span>图片尺寸</span>
                <el-select v-model="options.size" size="large">
                  <el-option
                    v-for="size in appStore.meta?.sizes || []"
                    :key="size.value"
                    :label="size.label"
                    :value="size.value"
                  />
                </el-select>
              </div>
              <div class="mini-field">
                <span>画质</span>
                <el-select v-model="options.quality" size="large">
                  <el-option
                    v-for="quality in appStore.meta?.qualities || []"
                    :key="quality.value"
                    :label="quality.label"
                    :value="quality.value"
                  />
                </el-select>
              </div>
            </div>
            <p class="quality-note">部分 Gemini 分组仅支持 auto 画质，如遇参数报错请切回自动。</p>
            <div class="prompt-field">
              <div class="prompt-head">
                <span>补充要求</span>
                <small>{{ instruction.length }} / 500</small>
              </div>
              <el-input
                v-model="instruction"
                type="textarea"
                :rows="3"
                maxlength="500"
                show-word-limit
                resize="none"
                placeholder="例如：偏法式通勤、自然微笑、背景更干净……"
              />
              <div class="hint-chips">
                <button
                  v-for="hint in hints"
                  :key="hint"
                  type="button"
                  class="hint-chip"
                  @click="useHint(hint)"
                >+ {{ hint }}</button>
              </div>
            </div>
          </div>
        </details>

        <div v-if="formError" class="form-error">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ formError }}</span>
        </div>

        <div class="generate-block">
          <el-button
            class="generate-btn"
            type="primary"
            size="large"
            :loading="submitting"
            :disabled="!canGenerate"
            @click="submit"
          >
            <el-icon v-if="!submitting"><MagicStick /></el-icon>
            {{ jobStore.isWorking ? '正在生成…' : isFiveShots ? '生成五张套图' : '开始生成' }}
            <el-icon v-if="!jobStore.isWorking && !submitting" class="btn-arrow"><ArrowRight /></el-icon>
          </el-button>
          <p v-if="disabledReason" class="generate-note">{{ disabledReason }}</p>
          <p v-else-if="isFiveShots" class="generate-note">
            五图套图会串行调用 5 次接口，产生 5 张图的费用；结果会逐张保存。
          </p>
          <p v-else class="generate-note">单次生成由中转站计费，结果会自动保存到作品库。</p>
        </div>
      </section>

      <section ref="stageRef" class="stage-column">
        <div class="stage-card">
          <div class="stage-head">
            <div class="stage-title">
              <span class="eyebrow">LIVE PREVIEW</span>
              <strong>{{ workflowLabel }}</strong>
            </div>
            <div class="stage-head-actions">
              <span v-if="displayJob?.parent_job_id" class="revision-badge">
                定向改图
              </span>
              <span v-if="displayJob" class="status-tag" :class="statusClass">
                <i></i>{{ statusText }}
              </span>
              <button
                v-if="previewJob"
                type="button"
                class="icon-button"
                title="关闭预览"
                @click="previewJob = null"
              >
                <el-icon><Close /></el-icon>
              </button>
            </div>
          </div>

          <div class="stage-body" :class="{ 'is-result': displayJob?.status === 'succeeded' && currentOutput }">
            <EmptyStage v-if="!displayJob || displayJob.status === 'canceled'" />

            <div v-else-if="isBusy" class="stage-busy">
              <img
                v-if="displayJob.inputs[0]"
                class="stage-busy-bg"
                :src="displayJob.inputs[0].asset.url"
                alt=""
              />
              <div class="stage-busy-overlay">
                <div class="orbital-loader"><span></span></div>
                <span class="eyebrow">{{ displayJob.status === 'queued' ? 'IN QUEUE' : 'GENERATING' }}</span>
                <h3>
                  {{ displayJob.status === 'queued'
                    ? '任务排队中'
                    : isFiveShots
                      ? `正在生成第 ${Math.min(displayJob.shots_done + 1, displayJob.shots_total)} / ${displayJob.shots_total} 张`
                      : '正在把衣服放进画面' }}
                </h3>
                <p>
                  {{ displayJob.status === 'queued'
                    ? '马上开始，请稍候片刻'
                    : isFiveShots
                      ? '主图完成后会作为后续四张的人物与系列一致性参考'
                      : '通常需要 30 秒到几分钟，请保持页面打开' }}
                </p>
                <div v-if="isFiveShots" class="series-progress">
                  <span :style="{ width: `${seriesProgress}%` }"></span>
                </div>
                <div class="elapsed-time">
                  {{ isFiveShots ? `${displayJob.shots_done} / ${displayJob.shots_total}` : formatElapsed(elapsedSeconds) }}
                </div>
                <button
                  v-if="displayJob.status === 'queued'"
                  type="button"
                  class="subtle-button"
                  @click="cancelActive"
                >取消排队</button>
              </div>
            </div>

            <div v-else-if="displayJob.status === 'failed'" class="stage-failed">
              <div class="error-mark">!</div>
              <span class="eyebrow">GENERATION FAILED</span>
              <h3>这次没有生成成功</h3>
              <p>{{ displayJob.error?.message || '生成失败，请稍后重试' }}</p>
              <p v-if="isFiveShots && displayJob.outputs.length" class="partial-note">
                已完成 {{ displayJob.shots_done }} / {{ displayJob.shots_total }} 张，已生成的图片已保留。
              </p>
              <div v-if="isFiveShots && displayJob.outputs.length" class="partial-results">
                <a
                  v-for="output in displayJob.outputs"
                  :key="output.id"
                  :href="output.download_url"
                  :download="output.original_name"
                  title="下载这张"
                >
                  <img :src="output.thumb_url || output.url" alt="" />
                </a>
              </div>
              <code v-if="displayJob.error?.code">{{ displayJob.error.code }}</code>
              <el-button type="primary" size="large" @click="retryActive">
                <el-icon><RefreshLeft /></el-icon>
                重新生成
              </el-button>
            </div>

            <div v-else-if="currentOutput" class="result-viewer">
              <img :src="currentOutput.url" :alt="displayJob.final_prompt.slice(0, 40)" />
            </div>

            <div v-if="displayJob?.outputs && displayJob.outputs.length > 1" class="result-thumbs">
              <button
                v-for="(output, index) in displayJob.outputs"
                :key="output.id"
                type="button"
                :class="{ active: selectedOutputIndex === index }"
                @click="selectedOutputIndex = index"
              >
                <img :src="output.thumb_url || output.url" :alt="`结果 ${index + 1}`" />
              </button>
            </div>
          </div>

          <div v-if="displayJob" class="stage-foot">
            <div class="stage-meta">
              <span>{{ displayJob.size }}</span>
              <span>{{ formatDate(displayJob.created_at) }}</span>
              <span v-if="displayJob.duration_ms">{{ formatDuration(displayJob.duration_ms) }}</span>
              <span v-else-if="displayJob.status === 'running'">{{ formatElapsed(elapsedSeconds) }}</span>
              <span v-if="displayJob.parent_job_id">改图任务</span>
              <span v-if="displayJob.shots_total > 1">
                {{ displayJob.shots_done }} / {{ displayJob.shots_total }} 张套图
              </span>
            </div>
            <div class="stage-actions">
              <a
                v-if="currentOutput"
                class="stage-action"
                :href="currentOutput.download_url"
                :download="currentOutput.original_name"
              >
                <el-icon><Download /></el-icon>下载原图
              </a>
              <button
                v-if="displayJob.final_prompt"
                type="button"
                class="stage-action"
                @click="promptOpen = true"
              >
                <el-icon><CopyDocument /></el-icon>查看提示词
              </button>
              <button
                v-if="displayJob.status === 'succeeded' && currentOutput && !jobStore.isWorking && displayJob.workflow !== 'five_shots'"
                type="button"
                class="stage-action is-primary"
                @click="openRevision"
              >
                <el-icon><MagicStick /></el-icon>调整这张
              </button>
              <button
                v-if="displayJob.status === 'succeeded'"
                type="button"
                class="stage-action"
                @click="useCurrentParams"
              >
                <el-icon><RefreshLeft /></el-icon>复用参数
              </button>
            </div>
          </div>
        </div>

        <div v-if="recentResults.length" class="recent-block">
          <div class="recent-head">
            <div>
              <span class="eyebrow">RECENT WORK</span>
              <h3>最近作品</h3>
            </div>
            <router-link to="/gallery" class="text-link">
              全部作品 <el-icon><ArrowRight /></el-icon>
            </router-link>
          </div>
          <div class="recent-strip">
            <button
              v-for="job in recentResults"
              :key="job.id"
              type="button"
              class="recent-item"
              @click="openRecent(job)"
            >
              <img :src="job.outputs[0].thumb_url || job.outputs[0].url" :alt="WORKFLOW_LABELS[job.workflow]" />
              <span>{{ WORKFLOW_LABELS[job.workflow] }}</span>
            </button>
          </div>
        </div>

        <div v-else class="stage-tip">
          <span class="tip-number">TIP</span>
          <p>建议上传正面、完整、背景干净的服装图。试穿模式下，服装细节保留得越完整，生成效果越稳定。</p>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="promptOpen"
      :title="displayJob?.workflow === 'five_shots' ? '五张图提示词' : '最终提示词'"
      width="680px"
      class="prompt-dialog"
    >
      <pre class="prompt-preview">{{ displayJob?.final_prompt }}</pre>
      <template #footer>
        <el-button @click="promptOpen = false">关闭</el-button>
        <el-button type="primary" @click="copyPrompt">复制提示词</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="revisionOpen" title="定向调整这张图" width="660px" class="revision-dialog">
      <div class="revision-layout">
        <div v-if="currentOutput" class="revision-preview">
          <img :src="currentOutput.thumb_url || currentOutput.url" alt="待调整的图片" />
        </div>
        <div class="revision-copy">
          <span class="eyebrow">TARGETED REVISION</span>
          <h3>只改问题，不动人物与服装</h3>
          <p>
            会以当前这张图作为改图对象，并继续带上原始服装图和模特参考。
            描述要具体，例如姿势、手指、皮肤、光线或褶皱，而不是简单重写“更真实”。
          </p>
          <div class="revision-hints">
            <button
              v-for="hint in revisionHints"
              :key="hint"
              type="button"
              class="hint-chip"
              @click="useRevisionHint(hint)"
            >+ {{ hint }}</button>
          </div>
        </div>
      </div>
      <el-input
        v-model="revisionFeedback"
        class="revision-input"
        type="textarea"
        :rows="4"
        maxlength="800"
        show-word-limit
        resize="none"
        placeholder="例如：站姿太僵，双手像展示式张开；皮肤磨皮太重；脚底缺少接触阴影。保持脸、发型和服装细节不变。"
      />
      <p class="revision-note">
        默认建议最多两轮定向修改；如果商品结构或人物身份仍不稳定，建议回到创作台重新生成。
      </p>
      <template #footer>
        <el-button @click="revisionOpen = false">取消</el-button>
        <el-button type="primary" :loading="revising" @click="submitRevision">
          <el-icon v-if="!revising"><MagicStick /></el-icon>
          开始调整
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
