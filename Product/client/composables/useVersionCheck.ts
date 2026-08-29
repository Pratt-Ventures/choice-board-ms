export function useVersionCheck() {
  const config = useRuntimeConfig()
  const { context, refreshContext } = useAuth()

  const clientVersion = computed(() => {
    const v = (config.public as Record<string, unknown>).appVersion as string | undefined
    const s = typeof v === 'string' ? v.trim() : ''
    return s || null
  })

  const serverVersion = computed(() => {
    const ctx = context.value as unknown as Record<string, unknown> | null
    const sv = ctx ? (ctx.server_version as string | null | undefined) : null
    if (typeof sv === 'string' && sv.trim()) return sv.trim()
    const cv = ctx ? (ctx.client_version as string | null | undefined) : null
    if (typeof cv === 'string' && cv.trim()) return cv.trim()
    return null
  })

  const mismatch = computed(() => {
    const cv = clientVersion.value
    const sv = serverVersion.value
    if (!cv || !sv) return false
    return cv !== sv
  })

  function storageKey(sv: string | null) {
    return `versionBannerDismissed:${sv || 'unknown'}`
  }

  const dismissed = ref(false)

  function syncDismissed() {
    if (!import.meta.client) return
    const sv = serverVersion.value
    if (!sv || !mismatch.value) {
      dismissed.value = false
      return
    }
    try {
      dismissed.value = sessionStorage.getItem(storageKey(sv)) === '1'
    } catch {
      dismissed.value = false
    }
  }

  watch([serverVersion, mismatch], () => syncDismissed(), { immediate: true })

  watch(mismatch, (isMismatch) => {
    if (isMismatch && import.meta.client) {
      // lightweight telemetry — console warn for staleness monitoring
      // eslint-disable-next-line no-console
      console.warn(
        `[version] client/server mismatch client=${clientVersion.value} server=${serverVersion.value} — reload to update`,
      )
    }
  })

  const showBanner = computed(() => mismatch.value && !dismissed.value)

  function dismiss() {
    if (!import.meta.client) return
    const sv = serverVersion.value
    if (!sv) return
    try {
      sessionStorage.setItem(storageKey(sv), '1')
    } catch {
      // ignore storage errors
    }
    dismissed.value = true
  }

  function reload() {
    if (!import.meta.client) return
    // Hard reload that bypasses HTTP cache and any CacheStorage entries.
    // Plain window.location.reload() may serve a cached index.html (especially
    // when served via StaticFiles without no-cache headers), so we best-effort
    // clear CacheStorage, bust the HTTP cache with a no-store fetch, and force
    // a network reload.
    try {
      const doHardReload = () => {
        // `true` param is deprecated but still forces a hard reload in some browsers
        try {
          ;(window.location.reload as unknown as (b: boolean) => void)(true)
        } catch {
          window.location.reload()
        }
        // Fallback: if the reload was still served from bfcache/disk, force navigation
        setTimeout(() => {
          if (document.visibilityState !== 'hidden') {
            window.location.href = window.location.href
          }
        }, 400)
      }
      const bustHttpCacheThenReload = () => {
        let done = false
        const once = () => {
          if (done) return
          done = true
          doHardReload()
        }
        try {
          fetch(window.location.href, {
            cache: 'no-store',
            headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
          }).then(once, once)
          setTimeout(once, 700)
        } catch {
          once()
        }
      }
      if ('caches' in window && typeof caches.keys === 'function') {
        caches
          .keys()
          .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
          .then(bustHttpCacheThenReload, bustHttpCacheThenReload)
        return
      }
      bustHttpCacheThenReload()
    } catch {
      window.location.reload()
    }
  }

  let pollTimer: ReturnType<typeof setInterval> | null = null

  function startPolling() {
    if (!import.meta.client) return
    if (pollTimer) return
    // re-check every 10 minutes for long-lived sessions
    pollTimer = setInterval(() => {
      refreshContext().catch(() => {})
    }, 10 * 60 * 1000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function onFocusReCheck() {
    refreshContext().catch(() => {})
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'visible') {
      refreshContext().catch(() => {})
    }
  }

  if (import.meta.client) {
    onMounted(() => {
      syncDismissed()
      startPolling()
      window.addEventListener('focus', onFocusReCheck)
      document.addEventListener('visibilitychange', onVisibilityChange)
    })
    onUnmounted(() => {
      stopPolling()
      window.removeEventListener('focus', onFocusReCheck)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    })
  }

  return {
    clientVersion,
    serverVersion,
    mismatch,
    showBanner,
    dismissed,
    dismiss,
    reload,
    refreshContext,
  }
}
