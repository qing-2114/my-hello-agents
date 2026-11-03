<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import { restoreTrip, saveTrip } from '@/services/tripStore'
import type { TripPlan } from '@/types'
import { exportPlan } from '@/services/export'

const savedPlan = restoreTrip()
// 编辑工作副本，避免取消或离开页面后污染已保存的内存状态。
const tripPlan = ref<TripPlan | null>(savedPlan ? JSON.parse(JSON.stringify(savedPlan)) : null)
const mapElement = ref<HTMLElement>()
const content = ref<HTMLElement>()
const mapStatus = ref('正在加载地图…')
const exporting = ref(false)
const editMode = ref(false)
const originalPlan = ref<TripPlan | null>(null)
const activeSection = ref('overview')
const sections = computed(() => [
  { key: 'overview', label: '行程概览' },
  ...(tripPlan.value?.budget ? [{ key: 'budget', label: '预算明细' }] : []),
  { key: 'map', label: '地图' }, { key: 'days', label: '每日行程' },
  ...((tripPlan.value?.weather_info.length || tripPlan.value?.weather_notes?.length) ? [{ key: 'weather', label: '天气' }] : [])
])
function scrollToSection(key: string) {
  activeSection.value = key
  document.getElementById(key)?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'
  })
}
function toggleEditMode() {
  if (!tripPlan.value) return
  originalPlan.value = JSON.parse(JSON.stringify(tripPlan.value))
  editMode.value = true
}
function moveAttraction(dayIndex: number, index: number, direction: 'up' | 'down') {
  const items = tripPlan.value?.days[dayIndex]?.attractions
  const target = index + (direction === 'up' ? -1 : 1)
  if (!editMode.value || !items || target < 0 || target >= items.length) return
  ;[items[index], items[target]] = [items[target], items[index]]
}
function deleteAttraction(dayIndex: number, index: number) {
  if (editMode.value) tripPlan.value?.days[dayIndex]?.attractions.splice(index, 1)
}
async function saveChanges() {
  if (!tripPlan.value) return
  const budget = tripPlan.value.budget
  if (budget) {
    budget.total_attractions = attractions.value.reduce((sum, item) => sum + (item.ticket_price ?? 0), 0)
    budget.total = budget.total_attractions + budget.total_hotels + budget.total_meals + budget.total_transportation
  }
  tripPlan.value.manually_edited = true
  saveTrip(JSON.parse(JSON.stringify(tripPlan.value)))
  originalPlan.value = null
  editMode.value = false
  message.success('修改已保存，门票预算已更新；交通与游览建议请按新顺序核实')
  await initMap()
}
function cancelEdit() {
  if (originalPlan.value) tripPlan.value = originalPlan.value
  originalPlan.value = null
  editMode.value = false
}
const failedImages = ref(new Set<string>())
const attractions = computed(() => tripPlan.value?.days.flatMap(day => day.attractions) ?? [])
const mealLabels: Record<string, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '小食' }
function safeUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  try { return new URL(url).protocol === 'https:' ? url : undefined } catch { return undefined }
}
function creditUrl(url?: string | null): string | undefined {
  const safe = safeUrl(url)
  if (!safe) return undefined
  const link = new URL(safe)
  link.searchParams.set('utm_source', 'trip_assistant')
  link.searchParams.set('utm_medium', 'referral')
  return link.href
}
let disposed = false
let map: { destroy(): void } | undefined
let mapRevision = 0

function imageFailed(url: string) { failedImages.value.add(url) }
async function initMap() {
  const revision = ++mapRevision
  map?.destroy()
  map = undefined
  mapStatus.value = '正在加载地图…'
  if (!tripPlan.value || !mapElement.value) return
  const key = import.meta.env.VITE_AMAP_WEB_KEY
  if (!key) { mapStatus.value = '配置高德 Web JS API Key 后即可查看景点地图。'; return }
  if (!attractions.value.length) { mapStatus.value = '暂无景点坐标'; return }
  try {
    const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE
    if (securityCode) (window as Window & { _AMapSecurityConfig?: { securityJsCode: string } })._AMapSecurityConfig = { securityJsCode: securityCode }
    const AMap = await AMapLoader.load({ key, version: '2.0' })
    if (disposed || revision !== mapRevision) return
    const first = attractions.value[0].location
    const instance = new AMap.Map(mapElement.value, {
      zoom: 12, center: [first.longitude, first.latitude], scrollWheel: false
    })
    map = instance
    let index = 0
    for (const day of tripPlan.value.days) {
      for (const attraction of day.attractions) {
        instance.add(new AMap.Marker({
          position: [attraction.location.longitude, attraction.location.latitude],
          title: attraction.name,
          label: { content: `${++index}`, direction: 'top' }
        }))
      }
    }
    instance.setFitView()
    mapStatus.value = ''
  } catch { mapStatus.value = '地图暂时无法加载，请检查网络或高德 Key 配置。行程仍可查看。' }
}
onMounted(initMap)
onBeforeUnmount(() => { disposed = true; map?.destroy() })

async function exportResult(format: 'png' | 'pdf') {
  if (!content.value || !tripPlan.value || exporting.value || editMode.value) return
  exporting.value = true
  try {
    await exportPlan(content.value, `${tripPlan.value.city}旅行计划`, format)
    message.success('导出完成')
  } catch { message.error('导出失败，请重试。远程图片可能无法载入。') }
  finally { exporting.value = false }
}
</script>

<template>
  <div v-if="!tripPlan" class="page-shell empty-state">
    <p class="eyebrow">A JOURNEY STARTS HERE</p><h1>还没有旅行计划</h1>
    <p class="muted">先告诉我们你的目的地，开始规划第一段旅程。</p>
    <RouterLink to="/" class="primary-link">去规划旅行</RouterLink>
  </div>
  <div v-else class="page-shell result-page">
    <div class="result-toolbar"><RouterLink to="/">← 重新规划</RouterLink><a-space wrap>
      <template v-if="editMode"><a-button @click="cancelEdit">取消编辑</a-button><a-button type="primary" @click="saveChanges">保存修改</a-button></template>
      <a-button v-else :disabled="exporting" @click="toggleEditMode">编辑行程</a-button>
      <a-button :disabled="editMode" :loading="exporting" @click="exportResult('png')">导出图片</a-button>
      <a-button type="primary" :disabled="editMode" :loading="exporting" @click="exportResult('pdf')">导出 PDF</a-button>
    </a-space></div>
    <nav class="section-nav" aria-label="行程分区"><button v-for="section in sections" :key="section.key" :class="{ active: activeSection === section.key }" :aria-current="activeSection === section.key ? 'location' : undefined" @click="scrollToSection(section.key)">{{ section.label }}</button></nav>
    <a-alert v-if="editMode" message="编辑中：可调整当天景点顺序或删除景点。保存后更新地图与门票预算；取消可恢复。" type="info" show-icon class="space-bottom" />
    <div id="trip-plan-content" ref="content">
      <header id="overview" class="result-hero">
        <p class="eyebrow">YOUR JOURNEY, BEAUTIFULLY PLANNED</p>
        <h1>{{ tripPlan.city }}，出发吧。</h1>
        <p>{{ tripPlan.start_date }} — {{ tripPlan.end_date }} <span class="hero-divider">/</span> {{ tripPlan.days.length }} 天探索之旅</p>
      </header>
      <section class="suggestion-box"><h2>{{ tripPlan.manually_edited ? '原始出行建议' : '出行小贴士' }}</h2><p v-if="tripPlan.manually_edited" class="space-bottom"><strong>行程已手动调整，原始建议中的路线和费用可能已变化，请以下方最新景点和预算为准。</strong></p><p>{{ tripPlan.overall_suggestions }}</p></section>
      <section v-if="tripPlan.budget" id="budget" class="budget-section">
        <div class="section-heading"><h2>旅行预算</h2><span class="muted">每人估算 · 价格以实际为准</span></div>
        <div class="budget-grid">
          <div><span>景点门票</span><strong>¥{{ tripPlan.budget.total_attractions }}</strong></div>
          <div><span>住宿</span><strong>¥{{ tripPlan.budget.total_hotels }}</strong></div>
          <div><span>餐饮</span><strong>¥{{ tripPlan.budget.total_meals }}</strong></div>
          <div><span>交通</span><strong>¥{{ tripPlan.budget.total_transportation }}</strong></div>
          <div class="budget-total"><span>预计总费用</span><strong>¥{{ tripPlan.budget.total }}</strong></div>
        </div>
      </section>
      <section id="map" class="map-section">
        <div class="section-heading"><h2>沿途坐标</h2><span class="muted">标记序号对应下方景点顺序</span></div>
        <div class="map-wrap" data-map-export :data-locations="attractions.map(item => `${item.location.longitude},${item.location.latitude}`).join(';')"><div ref="mapElement" class="amap-container" aria-label="景点位置地图"></div><p v-if="mapStatus" class="map-placeholder" role="status">{{ mapStatus }}</p></div>
      </section>
      <section v-if="tripPlan.weather_info.length || tripPlan.weather_notes?.length" id="weather" class="weather-section">
        <div class="section-heading"><h2>天气参考</h2><span class="muted">仅展示已查询到的日期</span></div>
        <div class="weather-grid"><article v-for="weather in tripPlan.weather_info" :key="weather.date" class="weather-card">
          <strong>{{ weather.date }}</strong><p>{{ weather.day_weather }}{{ weather.night_weather !== weather.day_weather ? ` / ${weather.night_weather}` : '' }}</p>
          <b>{{ weather.night_temp }}° — {{ weather.day_temp }}°C</b>
          <small>{{ weather.temperature_basis === 'daily_range' ? '全天最低 / 最高温度' : '夜间 / 白天温度' }}</small>
          <small>{{ [weather.wind_direction, weather.wind_power].filter(Boolean).join(' · ') }}</small>
          <small v-if="weather.source">来源：<a v-if="weather.source_url" :href="weather.source_url" target="_blank" rel="noopener noreferrer">{{ weather.source }}</a><span v-else>{{ weather.source }}</span></small>
        </article></div>
        <p v-for="note in tripPlan.weather_notes || []" :key="note" class="muted">{{ note }}</p>
        <small v-if="tripPlan.weather_info.some(w => w.source === 'Open-Meteo')" class="muted">Open-Meteo 天气数据（CC BY 4.0），已转换为中文天气描述及整数摄氏度。</small>
      </section>
      <div id="days"><section v-for="(day, dayOffset) in tripPlan.days" :key="day.date" class="day-section">
        <div class="day-heading"><span class="day-badge">DAY {{ String(day.day_index + 1).padStart(2, '0') }}</span><div><h2>第 {{ day.day_index + 1 }} 天 · {{ day.date }}</h2><p class="muted">{{ day.date }} · {{ day.transportation }}</p></div></div>
        <p v-if="tripPlan.manually_edited" class="muted">原始路线说明（编辑后仅供参考）：</p><p>{{ day.description }}</p>
        <div class="attraction-grid"><article v-for="(attraction, index) in day.attractions" :key="`${attraction.name}-${index}`" class="attraction-card" :data-coordinate="`${attraction.name}（${attraction.location.longitude}, ${attraction.location.latitude}）`">
          <div v-if="editMode" class="edit-buttons" data-export-hidden>
            <a-button size="small" :disabled="index === 0" @click="moveAttraction(dayOffset, index, 'up')">上移</a-button>
            <a-button size="small" :disabled="index === day.attractions.length - 1" @click="moveAttraction(dayOffset, index, 'down')">下移</a-button>
            <a-popconfirm title="确定从当天行程删除这个景点？" ok-text="删除" cancel-text="取消" @confirm="deleteAttraction(dayOffset, index)"><a-button size="small" danger>删除</a-button></a-popconfirm>
          </div>
          <div class="attraction-image">
            <img v-if="safeUrl(attraction.image_url) && !failedImages.has(attraction.image_url!)" :src="safeUrl(attraction.image_url)" :alt="`${attraction.name}参考图片`" crossorigin="anonymous" @error="imageFailed(attraction.image_url!)" />
            <span v-else class="image-placeholder">{{ attraction.name.slice(0, 1) }}<small>风景，留待亲眼看见</small></span>
            <span class="stop-number">{{ tripPlan.days.slice(0, dayOffset).reduce((n, d) => n + d.attractions.length, 0) + index + 1 }}</span>
          </div>
          <div class="attraction-body"><span class="category">{{ attraction.category || '景点' }}</span><h3>{{ attraction.name }}</h3><p>{{ attraction.description }}</p><p class="muted">{{ attraction.address }}</p>
            <div class="attraction-meta"><span>游览 {{ attraction.visit_duration }} 分钟</span><span>门票估算 ¥{{ attraction.ticket_price ?? 0 }}</span><span v-if="attraction.rating != null">评分 {{ attraction.rating }}/5</span></div>
            <small v-if="attraction.image_url" class="muted">配图为搜索参考，可能与实际景点不同。</small>
            <small v-if="attraction.image_photographer" style="display:block">摄影：<a :href="creditUrl(attraction.image_photographer_url)" target="_blank" rel="noopener noreferrer">{{ attraction.image_photographer }}</a> / <a :href="creditUrl(attraction.image_source_url) || 'https://unsplash.com/?utm_source=trip_assistant&utm_medium=referral'" target="_blank" rel="noopener noreferrer">Unsplash</a></small>
          </div>
        </article></div>
        <p v-if="!day.attractions.length" class="muted">当天景点已清空，仍保留餐饮和住宿安排。</p>
        <div class="day-details"><div class="detail-card"><h3>一日三餐</h3><div v-for="(meal, i) in day.meals" :key="i" class="meal-row"><span class="meal-type">{{ mealLabels[meal.type] || meal.type }}</span><div><strong>{{ meal.name }}</strong><p v-if="meal.description" class="muted">{{ meal.description }}</p><small v-if="meal.address">{{ meal.address }}</small></div><span>¥{{ meal.estimated_cost ?? 0 }}</span></div></div>
          <div class="detail-card"><h3>今晚住哪里</h3><template v-if="day.hotel"><h4>{{ day.hotel.name }}</h4><p>{{ day.hotel.address }}</p><p class="muted">{{ day.hotel.type }} {{ day.hotel.distance }}</p><p v-if="day.hotel.rating">评分 {{ day.hotel.rating }}</p><strong>¥{{ day.hotel.estimated_cost ?? 0 }} / 晚（估算）</strong></template><p v-else>{{ day.accommodation }}</p></div>
        </div>
      </section></div>
      <p class="result-footnote">行程与费用仅供规划参考，出发前请核实开放时间、预订与天气。导出地图为静态截图；无法截图时显示景点坐标清单。</p>
    </div>
  </div>
</template>
