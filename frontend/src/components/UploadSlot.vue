<script setup lang="ts">
import { ref } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import type { Asset } from '@/types'

const props = withDefaults(
  defineProps<{
    label: string
    hint?: string
    asset?: Asset | null
    required?: boolean
    uploading?: boolean
    progress?: number
    compact?: boolean
  }>(),
  {
    hint: '',
    asset: null,
    required: false,
    uploading: false,
    progress: 0,
    compact: false,
  },
)

const emit = defineEmits<{
  select: [file: File]
  remove: []
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const dragging = ref(false)

function open() {
  if (props.uploading) return
  inputRef.value?.click()
}

function onChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('select', file)
  target.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  if (props.uploading) return
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('select', file)
}

function remove(event: MouseEvent) {
  event.stopPropagation()
  emit('remove')
}
</script>

<template>
  <div
    class="upload-slot"
    :class="{
      'has-asset': Boolean(asset),
      'is-uploading': uploading,
      'is-compact': compact,
      'is-dragging': dragging,
    }"
    role="button"
    tabindex="0"
    @click="open"
    @keydown.enter="open"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <template v-if="asset">
      <img
        class="upload-preview"
        :src="asset.thumb_url || asset.url"
        :alt="label"
        draggable="false"
      />
      <div class="upload-asset-meta">
        <span>{{ label }}</span>
        <span>{{ asset.width }} × {{ asset.height }}</span>
      </div>
      <button class="upload-remove" type="button" aria-label="移除图片" @click="remove">
        <el-icon><Delete /></el-icon>
      </button>
    </template>
    <template v-else>
      <span class="upload-plus"><el-icon><Plus /></el-icon></span>
      <span class="upload-label">
        {{ label }}
        <em v-if="required">必填</em>
      </span>
      <span v-if="hint" class="upload-hint">{{ hint }}</span>
    </template>

    <div v-if="uploading" class="upload-progress">
      <span :style="{ width: `${Math.max(progress, 6)}%` }"></span>
    </div>
    <div v-if="uploading" class="upload-progress-label">上传中 {{ progress }}%</div>

    <input
      ref="inputRef"
      class="upload-input"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      @change="onChange"
    />
  </div>
</template>
