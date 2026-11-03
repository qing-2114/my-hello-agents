import { shallowRef } from 'vue'
import type { TripPlan } from '../types'

const storageKey = 'trip-assistant:last-plan'
export const currentTrip = shallowRef<TripPlan | null>(null)

export function saveTrip(plan: TripPlan): void {
  currentTrip.value = plan
  try { sessionStorage.setItem(storageKey, JSON.stringify(plan)) } catch { /* 内存仍可使用。 */ }
}

export function restoreTrip(): TripPlan | null {
  if (currentTrip.value) return currentTrip.value
  try {
    const raw = sessionStorage.getItem(storageKey)
    if (!raw) return null
    const plan = JSON.parse(raw)
    if (typeof plan.city !== 'string' || !Array.isArray(plan.days) || !Array.isArray(plan.weather_info)) return null
    currentTrip.value = plan
    return plan
  } catch { return null }
}
