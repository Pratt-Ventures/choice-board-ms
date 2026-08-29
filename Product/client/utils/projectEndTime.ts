export function parseEndTime(value?: string | null): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatEndDateMdY(value?: string | null): string {
  const date = parseEndTime(value)
  if (!date) return ''
  return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`
}

export function localEndTimeIso(date: Date): string {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 0, 0).toISOString()
}

export function collectionIsClosed(value?: string | null, now: Date = new Date()): boolean {
  const end = parseEndTime(value)
  if (!end) return false
  return now.getTime() > end.getTime() + 60 * 60 * 1000
}

export function collectionEndingSoon(value?: string | null, now: Date = new Date()): boolean {
  const end = parseEndTime(value)
  if (!end) return false
  const t = now.getTime()
  const close = end.getTime()
  const hour = 60 * 60 * 1000
  return close - hour <= t && t <= close + hour
}

export function projectRemainingTimeCopy(value?: string | null, now: Date = new Date()): string | null {
  const end = parseEndTime(value)
  if (!end || now.getTime() >= end.getTime()) return null
  const days = Math.ceil((end.getTime() - now.getTime()) / 864e5)
  if (days <= 0) return null
  const onDate = formatEndDateMdY(value)
  let n = days
  let unit = days === 1 ? 'day' : 'days'
  if (days > 60) {
    n = Math.round(days / 30)
    unit = n === 1 ? 'month' : 'months'
  }
  else if (days > 20) {
    n = Math.round(days / 7)
    unit = n === 1 ? 'week' : 'weeks'
  }
  return `Comparisons on this project open ${n} more ${unit} on ${onDate}`
}
