/** 旅行助手的数据契约，与后端 Pydantic 模型对应。 */
export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string | null
  rating?: number | null
  image_url?: string | null
  image_photographer?: string | null
  image_photographer_url?: string | null
  image_source_url?: string | null
  ticket_price?: number
}

export interface Meal {
  /** 约定值：breakfast / lunch / dinner / snack。后端当前接受字符串。 */
  type: string
  name: string
  address?: string | null
  location?: Location | null
  description?: string | null
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location | null
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface DayPlan {
  date: string
  /** 从 0 开始。 */
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel | null
  attractions: Attraction[]
  meals: Meal[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  /** 摄氏度，接口返回纯数字。 */
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
  source?: string
  source_url?: string
  temperature_basis?: 'day_night' | 'daily_range'
}

export interface TripPlan {
  /** 前端保存的编辑标记，非生成请求字段。 */
  manually_edited?: boolean
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  weather_notes?: string[]
  overall_suggestions: string
  budget?: Budget | null
}

/** 实际提交给 POST /api/trip/plan 的请求。 */
export type WeatherSource = 'auto' | 'amap' | 'hko' | 'open_meteo'

export interface TripPlanRequest {
  weather_source?: WeatherSource
  city: string
  start_date: string
  end_date: string
  days: number
  preferences: string[]
  /** 每人预算上限（元），省略或 null 表示未设置。 */
  budget?: number | null
  transportation: string
  accommodation: string
}

/** 文本表单状态；提交前需将偏好和预算转换为 TripPlanRequest。 */
export interface TripPlanFormData extends Omit<TripPlanRequest, 'preferences' | 'budget'> {
  preferences: string
  budget: string
}
