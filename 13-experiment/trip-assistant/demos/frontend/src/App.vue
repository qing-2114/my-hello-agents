<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const mainContent = ref<HTMLElement>()
watch(() => route.fullPath, async () => {
  await nextTick()
  if (mainContent.value) mainContent.value.scrollTop = 0
})
</script>

<template>
  <header class="site-header">
    <RouterLink to="/" class="brand">行旅<span>TRAVEL COMPANION</span></RouterLink>
    <span class="header-note">让期待，成为旅程。</span>
  </header>
  <main ref="mainContent" id="main-content" tabindex="0" aria-label="旅行助手内容"><RouterView /></main>
  <footer class="site-footer">行旅 · 智能旅行助手 <span>基于 Hello Agents 学习实践</span></footer>
</template>
