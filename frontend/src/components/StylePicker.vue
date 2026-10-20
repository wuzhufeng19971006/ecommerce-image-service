<script setup lang="ts">
import { Check } from '@element-plus/icons-vue'
import type { StyleOption } from '@/types'

defineProps<{
  styles: StyleOption[]
  modelValue?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="style-grid">
    <button
      v-for="style in styles"
      :key="style.id"
      class="style-option"
      :class="{ active: modelValue === style.id }"
      type="button"
      @click="emit('update:modelValue', style.id)"
    >
      <span class="style-copy">
        <span class="style-label">{{ style.label }}</span>
        <span class="style-desc">{{ style.description }}</span>
      </span>
      <span class="style-check"><el-icon><Check /></el-icon></span>
    </button>
  </div>
</template>
