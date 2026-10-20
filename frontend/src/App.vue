<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useJobStore } from '@/stores/jobStore'

const appStore = useAppStore()
const jobStore = useJobStore()

onMounted(() => {
  void appStore.load()
  void jobStore.refreshRecent()
  void jobStore.resume()
})
</script>

<template>
  <router-view />
</template>
