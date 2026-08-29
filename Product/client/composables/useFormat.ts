export type StatusInfo = {
  label: string
  color: 'success' | 'info' | 'warning' | 'error' | 'grey' | 'default'
  icon: string
}

export function useFormat() {
  function formatDate(value?: string | null, withTime = false) {
    if (!value) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return withTime
      ? date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
      : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  }

  function timeAgo(value?: string | null) {
    if (!value) return '—'
    const ms = Date.now() - new Date(value).getTime()
    if (Number.isNaN(ms)) return '—'
    const s = ms / 1000
    if (s < 60) return 'just now'
    if (s < 3600) return `${Math.floor(s / 60)}m ago`
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`
    const d = Math.floor(s / 86400)
    return d < 30 ? `${d}d ago` : formatDate(value)
  }

  function initials(name?: string | null) {
    if (!name) return '?'
    return name
      .split(/\s+/)
      .filter(Boolean)
      .map(w => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase()
  }

  function maskSecret(value?: string | null, visible = 4) {
    if (!value) return '—'
    if (value.length <= visible * 2) return '•'.repeat(Math.min(value.length, 12))
    return `${value.slice(0, visible)}…${value.slice(-visible)}`
  }

  function formatCurrency(amount?: number | null, currency = 'USD') {
    const n = amount ?? 0
    try {
      return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: currency.toUpperCase(),
        maximumFractionDigits: n % 1 === 0 ? 0 : 2,
      }).format(n)
    }
    catch {
      return `$${n.toLocaleString()}`
    }
  }

  function formatDeltaPct(value?: number | null) {
    if (value === null || value === undefined) return null
    const sign = value > 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  function subscriptionStatus(
    serviceExpiration?: string | null,
    trialExpiration?: string | null,
    gracePeriodHours = 0,
  ): StatusInfo {
    if (!serviceExpiration) {
      return { label: 'No expiration', color: 'grey', icon: 'mdi-help-circle-outline' }
    }
    const now = Date.now()
    const exp = new Date(serviceExpiration).getTime()
    if (Number.isNaN(exp)) {
      return { label: 'Unknown', color: 'grey', icon: 'mdi-help-circle-outline' }
    }
    if (exp > now) {
      const trialExp = trialExpiration ? new Date(trialExpiration).getTime() : NaN
      if (!Number.isNaN(trialExp) && trialExp > now) {
        return { label: 'trial', color: 'info', icon: 'mdi-timer-sand' }
      }
      return { label: 'active', color: 'success', icon: 'mdi-check-circle-outline' }
    }
    if (gracePeriodHours > 0 && exp + gracePeriodHours * 36e5 > now) {
      return { label: 'grace', color: 'warning', icon: 'mdi-clock-alert-outline' }
    }
    return { label: 'expired', color: 'error', icon: 'mdi-close-circle-outline' }
  }

  function daysRemaining(expiration?: string | null) {
    if (!expiration) return null
    const exp = new Date(expiration)
    if (Number.isNaN(exp.getTime())) return null
    return Math.ceil((exp.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  }

  function daysLeftLabel(
    serviceExpiration?: string | null,
    trialExpiration?: string | null,
    gracePeriodHours = 0,
  ) {
    const st = subscriptionStatus(serviceExpiration, trialExpiration, gracePeriodHours)
    if (!serviceExpiration) return '—'
    const now = Date.now()
    const exp = new Date(serviceExpiration).getTime()
    if (Number.isNaN(exp)) return '—'
    if (st.label === 'grace') {
      const h = Math.max(1, Math.round((exp + gracePeriodHours * 36e5 - now) / 36e5))
      return `${h}h grace left`
    }
    if (st.label === 'expired') {
      return `expired ${Math.floor((now - exp) / 864e5)}d ago`
    }
    const d = Math.ceil((exp - now) / 864e5)
    return (st.label === 'trial' ? 'trial · ' : '') + `in ${d}d`
  }

  function webhookHost(url?: string | null) {
    if (!url) return '—'
    try {
      return new URL(url).host
    }
    catch {
      return url
    }
  }

  async function copyText(value: string, label = 'Value') {
    const snackbar = useSnackbar()
    try {
      await navigator.clipboard.writeText(value)
      snackbar.success(`${label} copied`)
    }
    catch {
      snackbar.error('Could not copy to clipboard')
    }
  }

  /** Copy plain text plus optional HTML (for rich paste into email/docs). */
  async function copyRich(plain: string, html?: string | null, label = 'Value') {
    const snackbar = useSnackbar()
    try {
      if (html && typeof ClipboardItem !== 'undefined') {
        const item = new ClipboardItem({
          'text/plain': new Blob([plain], { type: 'text/plain' }),
          'text/html': new Blob([html], { type: 'text/html' }),
        })
        await navigator.clipboard.write([item])
      }
      else {
        await navigator.clipboard.writeText(plain)
      }
      snackbar.success(`${label} copied`)
    }
    catch {
      try {
        await navigator.clipboard.writeText(plain)
        snackbar.success(`${label} copied`)
      }
      catch {
        snackbar.error('Could not copy to clipboard')
      }
    }
  }

  return {
    formatDate,
    timeAgo,
    initials,
    maskSecret,
    formatCurrency,
    formatDeltaPct,
    subscriptionStatus,
    daysRemaining,
    daysLeftLabel,
    webhookHost,
    copyText,
    copyRich,
  }
}
