import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', name: 'studio', component: () => import('@/views/StudioView.vue') },
        { path: 'gallery', name: 'gallery', component: () => import('@/views/GalleryView.vue') },
        { path: 'jobs', name: 'jobs', component: () => import('@/views/JobsView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
