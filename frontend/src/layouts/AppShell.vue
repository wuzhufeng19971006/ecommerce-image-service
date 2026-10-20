<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { List, MagicStick, Picture, WarningFilled } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/appStore'
import { useJobStore } from '@/stores/jobStore'

const route = useRoute()
const appStore = useAppStore()
const jobStore = useJobStore()

const pageTitle = computed(() => {
  if (route.name === 'gallery') return '作品库'
  if (route.name === 'jobs') return '任务记录'
  return '创作台'
})

const navItems = [
  { name: 'studio', to: '/', label: '创作台', icon: MagicStick },
  { name: 'gallery', to: '/gallery', label: '作品库', icon: Picture },
  { name: 'jobs', to: '/jobs', label: '任务记录', icon: List },
]

const statusLabel = computed(() => {
  if (appStore.mock) return '演示模式'
  if (appStore.configured) return '接口已连接'
  return '待配置'
})

const statusClass = computed(() => {
  if (appStore.mock) return 'is-demo'
  if (appStore.configured) return 'is-online'
  return 'is-offline'
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <router-link to="/" class="brand">
        <span class="brand-mark">衣</span>
        <span class="brand-copy">
          <strong>衣图</strong>
          <small>AI STUDIO</small>
        </span>
      </router-link>

      <nav class="side-nav" aria-label="主导航">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="nav-item"
          :class="{ 'is-active': route.name === item.name }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <span
            v-if="item.name === 'studio' && jobStore.isWorking"
            class="nav-live"
            title="有任务正在生成"
          ></span>
        </router-link>
      </nav>

      <div class="side-quote">
        <span>“</span>
        <p>让每一件衣服，先拥有自己的画面。</p>
      </div>

      <div class="side-foot">
        <div class="side-status" :class="statusClass">
          <i></i>
          <span>{{ statusLabel }}</span>
        </div>
        <p class="side-model">{{ appStore.model || '等待读取模型' }}</p>
      </div>
    </aside>

    <div class="app-main">
      <header class="topbar">
        <div class="topbar-left">
          <span class="topbar-kicker">WORKSPACE</span>
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="topbar-right">
          <span class="topbar-date">服装电商视觉工作台</span>
          <span class="status-pill" :class="statusClass">
            <i></i>
            {{ statusLabel }}
          </span>
        </div>
      </header>

      <main class="page-content">
        <div v-if="appStore.error" class="config-banner is-error">
          <el-icon><WarningFilled /></el-icon>
          <div>
            <strong>无法读取服务配置</strong>
            <p>{{ appStore.error }}</p>
          </div>
          <button type="button" class="text-button" @click="appStore.load(true)">重试</button>
        </div>

        <div v-else-if="appStore.config && !appStore.configured" class="config-banner">
          <el-icon><WarningFilled /></el-icon>
          <div>
            <strong>还差一步：配置生图接口</strong>
            <p>
              复制项目根目录的 <code>.env.example</code> 为 <code>.env</code>，填写
              <code>IMAGE_API_BASE</code>、<code>IMAGE_API_KEY</code> 和 <code>IMAGE_MODEL</code>，
              然后重启后端。
            </p>
          </div>
        </div>

        <div v-if="appStore.mock" class="demo-banner">
          <span class="demo-dot"></span>
          演示模式已开启：当前生成的是占位图，不会调用真实接口或产生费用。
        </div>

        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>
