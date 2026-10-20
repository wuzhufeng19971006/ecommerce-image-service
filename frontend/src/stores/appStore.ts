import { defineStore } from 'pinia'
import { fetchConfig, fetchMeta, formatApiError } from '@/api/client'
import type { AppConfig, Meta } from '@/types'

export const useAppStore = defineStore('app', {
  state: () => ({
    config: null as AppConfig | null,
    meta: null as Meta | null,
    loading: false,
    error: '',
  }),
  getters: {
    configured: (state) => Boolean(state.config?.configured),
    mock: (state) => Boolean(state.config?.mock),
    model: (state) => state.config?.model || '',
    workflows: (state) => state.meta?.workflows || [],
  },
  actions: {
    async load(force = false) {
      if (this.loading) return
      if (this.config && this.meta && !force) return
      this.loading = true
      this.error = ''
      try {
        const [config, meta] = await Promise.all([fetchConfig(), fetchMeta()])
        this.config = config
        this.meta = meta
      } catch (error) {
        this.error = formatApiError(error)
      } finally {
        this.loading = false
      }
    },
  },
})
