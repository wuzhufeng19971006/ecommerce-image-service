<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Download, Picture, Refresh } from '@element-plus/icons-vue'
import { fetchGallery, formatApiError } from '@/api/client'
import type { GalleryItem, WorkflowId } from '@/types'
import GalleryCard from '@/components/GalleryCard.vue'
import { useAppStore } from '@/stores/appStore'
import {
  WORKFLOW_LABELS,
  formatDate,
  formatDuration,
} from '@/utils/format'

const appStore = useAppStore()
const router = useRouter()

const items = ref<GalleryItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 16
const filter = ref<'all' | WorkflowId>('all')
const loading = ref(false)
const error = ref('')
const selected = ref<GalleryItem | null>(null)
const dialogVisible = ref(false)

const filters = computed(() => {
  const workflows = appStore.workflows.map((item) => ({
    id: item.id as WorkflowId,
    label: item.label,
  }))
  const fallback = (Object.keys(WORKFLOW_LABELS) as WorkflowId[]).map((id) => ({
    id,
    label: WORKFLOW_LABELS[id],
  }))
  return [{ id: 'all' as const, label: '全部' }, ...(workflows.length ? workflows : fallback)]
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await fetchGallery({
      page: page.value,
      page_size: pageSize,
      workflow: filter.value === 'all' ? undefined : filter.value,
    })
    items.value = result.items
    total.value = result.total
  } catch (err) {
    error.value = formatApiError(err)
  } finally {
    loading.value = false
  }
}

watch(filter, () => {
  page.value = 1
  void load()
})

watch(page, () => void load())

onMounted(() => {
  void appStore.load()
  void load()
})

function view(item: GalleryItem) {
  selected.value = item
  dialogVisible.value = true
}

function reuse() {
  if (!selected.value) return
  const id = selected.value.job_id
  dialogVisible.value = false
  void router.push({ path: '/', query: { reuse: id } })
}
</script>

<template>
  <section class="gallery-page">
    <header class="page-hero compact-hero">
      <div class="page-hero-copy">
        <span class="eyebrow">SELECTED WORK</span>
        <h2>作品库</h2>
        <p>每一次生成都会留在这里。挑一张继续打磨，或下载用于商品页面。</p>
      </div>
      <div class="gallery-count">
        <strong>{{ total }}</strong>
        <span>张成品</span>
      </div>
    </header>

    <div class="filter-bar">
      <div class="filter-pills">
        <button
          v-for="item in filters"
          :key="item.id"
          type="button"
          class="filter-pill"
          :class="{ active: filter === item.id }"
          @click="filter = item.id"
        >{{ item.label }}</button>
      </div>
      <button type="button" class="refresh-button" :disabled="loading" @click="load">
        <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
        刷新
      </button>
    </div>

    <div v-if="error" class="inline-error">
      <span>{{ error }}</span>
      <button type="button" class="text-button" @click="load">重试</button>
    </div>

    <div v-if="loading && !items.length" class="gallery-masonry">
      <div v-for="n in 8" :key="n" class="gallery-skeleton" :class="`skeleton-${n % 3}`"></div>
    </div>

    <div v-else-if="items.length" class="gallery-masonry">
      <GalleryCard v-for="item in items" :key="`${item.job_id}-${item.output.id}`" :item="item" @view="view" />
    </div>

    <div v-else class="empty-page">
      <div class="empty-page-icon"><el-icon><Picture /></el-icon></div>
      <span class="eyebrow">NOTHING HERE YET</span>
      <h3>作品库还是空的</h3>
      <p>去创作台生成第一张服装图，它会自动出现在这里。</p>
      <router-link to="/" class="primary-link">去创作 <el-icon><ArrowRight /></el-icon></router-link>
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

    <el-dialog v-model="dialogVisible" title="作品详情" width="980px" class="gallery-dialog">
      <div v-if="selected" class="gallery-detail">
        <div class="gallery-detail-image">
          <img :src="selected.output.url" :alt="selected.final_prompt.slice(0, 40)" />
        </div>
        <div class="gallery-detail-copy">
          <span class="eyebrow">IMAGE DETAIL</span>
          <h3>{{ WORKFLOW_LABELS[selected.workflow] }}</h3>
          <div class="detail-meta">
            <span>{{ selected.options.size }}</span>
            <span>{{ formatDate(selected.created_at) }}</span>
            <span>{{ selected.output.width }} × {{ selected.output.height }}</span>
          </div>
          <p class="detail-instruction" v-if="selected.instruction">
            {{ selected.instruction }}
          </p>
          <div class="detail-prompt">
            <span>最终提示词</span>
            <p>{{ selected.final_prompt }}</p>
          </div>
          <div class="detail-actions">
            <a
              class="primary-link"
              :href="selected.output.download_url"
              :download="selected.output.original_name"
            >
              <el-icon><Download /></el-icon> 下载原图
            </a>
            <button type="button" class="secondary-link" @click="reuse">
              复用这组参数 <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </el-dialog>
  </section>
</template>
