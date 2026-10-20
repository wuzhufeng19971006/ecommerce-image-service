<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  CircleClose,
  RefreshLeft,
  View,
  WarningFilled,
} from '@element-plus/icons-vue'
import {
  cancelJob,
  formatApiError,
  listJobs,
} from '@/api/client'
import type { Job, JobStatus, WorkflowId } from '@/types'
import { useAppStore } from '@/stores/appStore'
import { useJobStore } from '@/stores/jobStore'
import {
  STATUS_LABELS,
  WORKFLOW_LABELS,
  formatDate,
  formatDuration,
} from '@/utils/format'

const appStore = useAppStore()
const jobStore = useJobStore()
const router = useRouter()

const jobs = ref<Job[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 12
const statusFilter = ref<'all' | JobStatus>('all')
const workflowFilter = ref<'all' | WorkflowId>('all')
const loading = ref(false)
const error = ref('')
const selected = ref<Job | null>(null)
const dialogVisible = ref(false)

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '生成中' },
  { value: 'succeeded', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'canceled', label: '已取消' },
]

const workflowOptions = computed(() => [
  { value: 'all', label: '全部模式' },
  ...appStore.workflows.map((item) => ({ value: item.id, label: item.label })),
])

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await listJobs({
      page: page.value,
      page_size: pageSize,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      workflow: workflowFilter.value === 'all' ? undefined : workflowFilter.value,
    })
    jobs.value = result.items
    total.value = result.total
  } catch (err) {
    error.value = formatApiError(err)
  } finally {
    loading.value = false
  }
}

watch([statusFilter, workflowFilter], () => {
  page.value = 1
  void load()
})

watch(page, () => void load())

onMounted(() => {
  void appStore.load()
  void load()
})

function statusClass(status: JobStatus): string {
  if (status === 'succeeded') return 'is-success'
  if (status === 'failed') return 'is-failed'
  if (status === 'canceled') return 'is-canceled'
  return 'is-running'
}

function view(job: Job) {
  selected.value = job
  dialogVisible.value = true
}

async function retry(job: Job) {
  try {
    await jobStore.retry(job.id)
    dialogVisible.value = false
    ElMessage.success('已重新提交生成任务')
    void router.push('/')
  } catch (err) {
    ElMessage.error(formatApiError(err))
  }
}

async function cancel(job: Job) {
  try {
    await cancelJob(job.id)
    ElMessage.success('已取消排队任务')
    await load()
  } catch (err) {
    ElMessage.error(formatApiError(err))
  }
}

function styleLabel(job: Job): string {
  const workflow = appStore.workflows.find((item) => item.id === job.workflow)
  return workflow?.styles.find((style) => style.id === job.options.style)?.label || '默认风格'
}

function summary(job: Job): string {
  if (job.error?.message) return job.error.message
  if (job.instruction) return job.instruction
  const progress =
    job.shots_total > 1 ? `${job.shots_done}/${job.shots_total} 张 · ` : ''
  return `${progress}${styleLabel(job)} · ${job.options.size}`
}

function roleLabel(role: string, workflow?: WorkflowId): string {
  if (role === 'garment') return workflow === 'five_shots' ? '商品图 1' : '服装'
  if (role === 'model') return '模特'
  if (role === 'approved') return '认可成片'
  if (role === 'edit_target') return '改图对象'
  return workflow === 'five_shots' ? '商品图 2' : '参考'
}
</script>

<template>
  <section class="jobs-page">
    <header class="page-hero compact-hero">
      <div class="page-hero-copy">
        <span class="eyebrow">GENERATION LOG</span>
        <h2>任务记录</h2>
        <p>排队、生成、失败与完成，每一次调用都有迹可循。</p>
      </div>
      <div class="gallery-count">
        <strong>{{ total }}</strong>
        <span>条记录</span>
      </div>
    </header>

    <div class="filter-bar">
      <div class="filter-selects">
        <el-select v-model="statusFilter" size="large" style="width: 148px">
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="workflowFilter" size="large" style="width: 156px">
          <el-option
            v-for="item in workflowOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </div>
      <button type="button" class="refresh-button" :disabled="loading" @click="load">
        <el-icon :class="{ spinning: loading }"><RefreshLeft /></el-icon>
        刷新
      </button>
    </div>

    <div v-if="error" class="inline-error">
      <span>{{ error }}</span>
      <button type="button" class="text-button" @click="load">重试</button>
    </div>

    <div v-if="jobs.length" class="jobs-table">
      <div class="jobs-thead">
        <span>任务</span>
        <span>状态</span>
        <span>创建时间</span>
        <span>耗时</span>
        <span class="align-right">操作</span>
      </div>
      <div v-for="job in jobs" :key="job.id" class="job-row" @click="view(job)">
        <div class="job-cell job-identity">
          <div class="job-thumb">
            <img
              v-if="job.outputs[0]"
              :src="job.outputs[0].thumb_url || job.outputs[0].url"
              alt=""
            />
            <span v-else class="job-thumb-placeholder">{{ WORKFLOW_LABELS[job.workflow].slice(0, 1) }}</span>
          </div>
          <div class="job-copy">
            <strong>
              {{ WORKFLOW_LABELS[job.workflow] }}
              <span v-if="job.parent_job_id" class="revision-badge">改图</span>
            </strong>
            <p>{{ summary(job) }}</p>
          </div>
        </div>
        <div class="job-cell">
          <span class="status-tag" :class="statusClass(job.status)">
            <i></i>{{ STATUS_LABELS[job.status] }}
          </span>
        </div>
        <div class="job-cell job-date">{{ formatDate(job.created_at, true) }}</div>
        <div class="job-cell job-duration">{{ formatDuration(job.duration_ms) }}</div>
        <div class="job-cell job-actions" @click.stop>
          <button type="button" class="icon-button" title="查看详情" @click="view(job)">
            <el-icon><View /></el-icon>
          </button>
          <button
            v-if="job.status === 'failed' || job.status === 'succeeded'"
            type="button"
            class="icon-button"
            title="重试 / 再生成"
            @click="retry(job)"
          >
            <el-icon><RefreshLeft /></el-icon>
          </button>
          <button
            v-if="job.status === 'queued'"
            type="button"
            class="icon-button danger"
            title="取消排队"
            @click="cancel(job)"
          >
            <el-icon><CircleClose /></el-icon>
          </button>
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty-page">
      <div class="empty-page-icon"><el-icon><WarningFilled /></el-icon></div>
      <span class="eyebrow">NO TASKS YET</span>
      <h3>还没有任务记录</h3>
      <p>去创作台提交第一张图，任务状态会实时显示在这里。</p>
      <router-link to="/" class="primary-link">去创作 <el-icon><ArrowRight /></el-icon></router-link>
    </div>

    <div v-else class="jobs-loading">
      <div v-for="n in 5" :key="n" class="job-skeleton"></div>
    </div>

    <div v-if="total > pageSize" class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        background
      />
    </div>

    <el-dialog v-model="dialogVisible" title="任务详情" width="820px" class="job-dialog">
      <div v-if="selected" class="job-detail">
        <div class="job-detail-head">
          <div>
            <span class="eyebrow">TASK DETAIL</span>
            <h3>
              {{ WORKFLOW_LABELS[selected.workflow] }}
              <span v-if="selected.parent_job_id" class="revision-badge">定向改图</span>
            </h3>
            <div class="detail-meta">
              <span>{{ formatDate(selected.created_at, true) }}</span>
              <span>{{ selected.options.size }}</span>
              <span>{{ selected.model }}</span>
              <span v-if="selected.shots_total > 1">
                {{ selected.shots_done }} / {{ selected.shots_total }} 张套图
              </span>
            </div>
          </div>
          <span class="status-tag" :class="statusClass(selected.status)">
            <i></i>{{ STATUS_LABELS[selected.status] }}
          </span>
        </div>

        <div v-if="selected.outputs.length" class="job-outputs">
          <img
            v-for="output in selected.outputs"
            :key="output.id"
            :src="output.url"
            :alt="selected.final_prompt.slice(0, 30)"
          />
        </div>

        <div v-if="selected.error" class="job-error-box">
          <strong>{{ selected.error.message }}</strong>
          <code>{{ selected.error.code }}</code>
        </div>

        <div class="job-inputs">
          <span class="detail-label">参考素材</span>
          <div class="job-input-thumbs">
            <div v-for="input in selected.inputs" :key="input.asset.id" class="job-input-thumb">
              <img :src="input.asset.thumb_url || input.asset.url" alt="" />
              <span>{{ roleLabel(input.role, selected.workflow) }}</span>
            </div>
          </div>
        </div>

        <div class="detail-prompt">
          <span>最终提示词</span>
          <p>{{ selected.final_prompt }}</p>
        </div>

        <div class="detail-actions">
          <a
            v-if="selected.outputs[0]"
            class="primary-link"
            :href="selected.outputs[0].download_url"
            :download="selected.outputs[0].original_name"
          >下载原图</a>
          <button
            v-if="selected.status === 'failed' || selected.status === 'succeeded'"
            type="button"
            class="secondary-link"
            @click="retry(selected)"
          >
            重试 / 再生成 <el-icon><ArrowRight /></el-icon>
          </button>
        </div>
      </div>
    </el-dialog>
  </section>
</template>
