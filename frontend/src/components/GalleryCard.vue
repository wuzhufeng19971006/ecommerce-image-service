<script setup lang="ts">
import { Download, View } from '@element-plus/icons-vue'
import type { GalleryItem } from '@/types'
import { WORKFLOW_LABELS, formatDate } from '@/utils/format'

defineProps<{
  item: GalleryItem
}>()

const emit = defineEmits<{
  view: [item: GalleryItem]
}>()
</script>

<template>
  <article class="gallery-card" @click="emit('view', item)">
    <div
      class="gallery-image-wrap"
      :style="{ aspectRatio: `${item.output.width} / ${item.output.height}` }"
    >
      <img
        class="gallery-image"
        :src="item.output.thumb_url || item.output.url"
        :alt="item.final_prompt.slice(0, 40)"
        loading="lazy"
      />
      <div class="gallery-hover">
        <button type="button" class="gallery-action" @click.stop="emit('view', item)">
          <el-icon><View /></el-icon>
          查看
        </button>
        <a
          class="gallery-action"
          :href="item.output.download_url"
          :download="item.output.original_name"
          @click.stop
        >
          <el-icon><Download /></el-icon>
          下载
        </a>
      </div>
    </div>
    <div class="gallery-meta">
      <span class="gallery-workflow">{{ WORKFLOW_LABELS[item.workflow] }}</span>
      <span class="gallery-date">{{ formatDate(item.created_at) }}</span>
    </div>
  </article>
</template>
