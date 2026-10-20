<script setup lang="ts">
import type { Component } from 'vue'
import { Files, Location, Picture, User, ZoomIn } from '@element-plus/icons-vue'
import type { WorkflowId, WorkflowMeta } from '@/types'

defineProps<{
  workflows: WorkflowMeta[]
  modelValue: WorkflowId
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WorkflowId]
}>()

const ICONS: Record<WorkflowId, Component> = {
  try_on: User,
  white_bg: Picture,
  scene: Location,
  detail: ZoomIn,
  five_shots: Files,
}
</script>

<template>
  <div class="workflow-grid">
    <button
      v-for="(workflow, index) in workflows"
      :key="workflow.id"
      class="workflow-card"
      :class="{ active: modelValue === workflow.id }"
      type="button"
      @click="emit('update:modelValue', workflow.id)"
    >
      <span class="workflow-index">{{ String(index + 1).padStart(2, '0') }}</span>
      <span class="workflow-icon">
        <el-icon><component :is="ICONS[workflow.id]" /></el-icon>
      </span>
      <span class="workflow-name">{{ workflow.label }}</span>
      <span class="workflow-desc">{{ workflow.description }}</span>
    </button>
  </div>
</template>
