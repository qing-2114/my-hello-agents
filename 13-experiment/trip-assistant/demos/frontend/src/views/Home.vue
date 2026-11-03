<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import axios from 'axios'
import { generateTripPlan } from '@/services/api'
import { saveTrip } from '@/services/tripStore'
import type { TripPlanRequest, WeatherSource } from '@/types'

const router = useRouter()
const loading = ref(false)
const loadingProgress = ref(0)
const errorText = ref('')
const formData = reactive({
  weather_source: 'auto' as WeatherSource,
  city: '', start_date: '', end_date: '', preferences: ['历史文化'],
  budget: null as number | null, transportation: '公共交通', accommodation: '经济型酒店'
})
const dayCount = computed(() => {
  if (!formData.start_date || !formData.end_date) return 0
  return Math.round((Date.parse(formData.end_date) - Date.parse(formData.start_date)) / 86400000) + 1
})
const loadingStatus = computed(() => {
  if (loadingProgress.value === 100) return '规划完成！'
  if (loadingProgress.value <= 30) return '预计准备阶段：搜索景点…'
  if (loadingProgress.value <= 50) return '预计准备阶段：查询天气…'
  if (loadingProgress.value <= 70) return '预计准备阶段：推荐酒店…'
  return '预计整合阶段：生成行程与图片，请稍候…'
})
let timer: ReturnType<typeof setInterval> | undefined
onBeforeUnmount(() => clearInterval(timer))

async function handleSubmit() {
  if (loading.value) return
  errorText.value = ''
  if (!formData.city.trim() || !formData.start_date || !formData.end_date) {
    errorText.value = '请填写目的地和完整旅行日期。'; return
  }
  if (!Number.isFinite(dayCount.value) || dayCount.value < 1 || dayCount.value > 30) {
    errorText.value = '结束日期不能早于开始日期，行程需为 1–30 天。'; return
  }
  if (formData.budget !== null && (!Number.isInteger(formData.budget) || formData.budget < 0)) {
    errorText.value = '预算请输入非负整数，或留空。'; return
  }
  const request: TripPlanRequest = { ...formData, city: formData.city.trim(), days: dayCount.value }
  loading.value = true
  loadingProgress.value = 5
  timer = setInterval(() => { loadingProgress.value = Math.min(90, loadingProgress.value + 5) }, 3000)
  try {
    const plan = await generateTripPlan(request)
    saveTrip(plan)
    loadingProgress.value = 100
    await router.push({ name: 'result' })
  } catch (error) {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined
    errorText.value = axios.isAxiosError(error) && error.code === 'ECONNABORTED'
      ? '规划等待超过 5 分钟，请稍后重试或缩短行程。'
      : typeof detail === 'string' ? detail : '生成计划失败，请检查后端服务后重试。'
    message.error(errorText.value)
  } finally {
    clearInterval(timer)
    loading.value = false
  }
}
</script>

<template>
  <div class="home-layout page-shell">
    <section class="home-intro">
      <p class="eyebrow">YOUR NEXT JOURNEY</p>
      <h1>下一站，<br />去心之所向。</h1>
      <p class="intro-text">告诉我们你的期待。把景点、美食与沿途风景，串成一份属于你的旅行计划。</p>
      <div class="journey-art" aria-hidden="true">
        <div class="sun"></div><div class="mountain mountain-back"></div><div class="mountain mountain-front"></div>
        <div class="art-caption">每一段旅程，都值得认真规划。<span>EXPLORE · DISCOVER · REMEMBER</span></div>
      </div>
      <div class="feature-row"><span>个性化行程</span><span>天气与住宿</span><span>地图与预算</span></div>
    </section>

    <a-card class="form-card" :bordered="false">
      <p class="eyebrow">PLAN YOUR TRIP</p><h2>从一个目的地开始</h2>
      <p class="muted">填写旅行偏好，我们来安排沿途精彩。</p>
      <a-form layout="vertical" :model="formData" @finish="handleSubmit" :disabled="loading">
        <a-form-item label="目的地城市" name="city" :rules="[{ required: true, whitespace: true, message: '请输入目的地城市' }]">
          <a-input v-model:value="formData.city" size="large" placeholder="想去哪里？例如：北京" :maxlength="50" />
        </a-form-item>
        <div class="form-grid">
          <a-form-item label="出发日期" name="start_date" :rules="[{ required: true, message: '请选择出发日期' }]">
            <input id="start-date" v-model="formData.start_date" type="date" aria-label="出发日期" :disabled="loading" required />
          </a-form-item>
          <a-form-item label="结束日期" name="end_date" :rules="[{ required: true, message: '请选择结束日期' }]">
            <input id="end-date" v-model="formData.end_date" type="date" aria-label="结束日期" :min="formData.start_date" :disabled="loading" required />
          </a-form-item>
        </div>
        <p class="date-hint">{{ dayCount > 0 ? `共 ${dayCount} 天 · 包含出发和结束当天` : '选择日期后自动计算旅行天数，最多 30 天' }}</p>
        <a-form-item label="你喜欢怎样的旅行" name="preferences">
          <a-select v-model:value="formData.preferences" mode="tags" size="large" placeholder="选择或输入偏好" :options="['历史文化', '自然风光', '城市漫步', '当地美食', '亲子休闲', '艺术博物馆'].map(value => ({ value }))" />
        </a-form-item>
        <div class="form-grid">
          <a-form-item label="交通方式" name="transportation"><a-select v-model:value="formData.transportation" size="large" :options="['公共交通', '自驾', '步行与公共交通', '出租车'].map(value => ({ value }))" /></a-form-item>
          <a-form-item label="住宿偏好" name="accommodation"><a-select v-model:value="formData.accommodation" size="large" :options="['经济型酒店', '舒适型酒店', '高档酒店', '特色民宿'].map(value => ({ value }))" /></a-form-item>
        </div>
        <a-form-item label="天气数据源" name="weather_source">
          <a-select v-model:value="formData.weather_source" size="large" :options="[
            { value: 'auto', label: '自动选择（香港优先天文台）' },
            { value: 'hko', label: '优先香港天文台（仅香港）' },
            { value: 'open_meteo', label: '优先 Open-Meteo（全球）' },
            { value: 'amap', label: '优先高德天气' }
          ]" />
          <small class="muted">所选来源不可用或缺少日期时，自动尝试其他来源。</small>
        </a-form-item>
        <a-form-item label="每人总预算（元，可选）" name="budget"><a-input-number v-model:value="formData.budget" :min="0" :precision="0" :step="100" size="large" placeholder="留空表示不限预算" style="width: 100%" /></a-form-item>
        <a-alert v-if="errorText" :message="errorText" type="error" show-icon class="space-bottom" role="alert" />
        <a-button type="primary" html-type="submit" size="large" block :loading="loading">{{ loading ? '正在为你规划' : '开始规划我的旅程' }}</a-button>
        <div v-if="loading" class="loading-box" role="status" aria-live="polite">
          <a-progress :percent="loadingProgress" :show-info="false" status="active" />
          <p>{{ loadingStatus }}</p><small>进度为等待估算，不代表实际任务完成比例。</small>
        </div>
      </a-form>
    </a-card>
  </div>
</template>
