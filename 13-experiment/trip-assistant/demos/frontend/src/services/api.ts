import axios from 'axios'
import type { TripPlanRequest, TripPlan } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 300000, // 多 Agent 串行调用及备用模型切换可能超过2分钟。
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  config => {
    console.debug('发送请求：', config.method?.toUpperCase(), config.url)
    return config
  },
  error => Promise.reject(error)
)

api.interceptors.response.use(
  response => {
    console.debug('收到响应：', response.status, response.config.url)
    return response
  },
  error => {
    if (axios.isAxiosError(error)) {
      console.error('请求失败：', error.code, error.response?.status)
    } else {
      console.error('请求失败：未知错误')
    }
    return Promise.reject(error)
  }
)

/** 后端直接返回 TripPlan，无额外的 data 包装层。 */
export const generateTripPlan = async (request: TripPlanRequest): Promise<TripPlan> => {
  const response = await api.post<TripPlan>('/trip/plan', request)
  return response.data
}
