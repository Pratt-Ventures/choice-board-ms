/**
 * Devtools helper: `version()` — print current client/server versions and banner debug info.
 *
 * Usage in Chrome DevTools console:
 *   version()        // logs clientVersion, serverVersion, mismatch, banner state, /status
 *   await version()  // same, but await the /status fetch and context refresh
 *
 * The function is attached to `window` and `globalThis` so `version()` works as a
 * bare global in the console (window properties are globals in devtools).
 * Safe to call on any page, including login / unauthenticated.
 */
export default defineNuxtPlugin(() => {
  if (import.meta.server) return

  const getClientVersion = (): string | null => {
    try {
      const cfg = useRuntimeConfig()
      const v = (cfg.public as Record<string, unknown>).appVersion as string | undefined
      const s = typeof v === 'string' ? v.trim() : ''
      return s || null
    } catch {
      return null
    }
  }

  const getContextVersions = (): {
    server_version: string | null
    client_version: string | null
    context_present: boolean
    context_raw: unknown
  } => {
    try {
      const { context } = useAuth()
      const ctx = context.value as unknown as Record<string, unknown> | null
      const sv = ctx ? (ctx.server_version as string | null | undefined) : null
      const cv = ctx ? (ctx.client_version as string | null | undefined) : null
      return {
        server_version: typeof sv === 'string' && sv.trim() ? sv.trim() : null,
        client_version: typeof cv === 'string' && cv.trim() ? cv.trim() : null,
        context_present: !!ctx && !!ctx.user_id,
        context_raw: ctx,
      }
    } catch {
      return { server_version: null, client_version: null, context_present: false, context_raw: null }
    }
  }

  const getBannerDebug = (serverVersion: string | null): {
    mismatch: boolean
    dismissed: boolean
    showBanner: boolean
    storageKey: string
    storageValue: string | null
    allDismissKeys: Record<string, string>
  } => {
    const clientVersion = getClientVersion()
    const mismatch = !!(clientVersion && serverVersion && clientVersion !== serverVersion)
    const storageKey = `versionBannerDismissed:${serverVersion || 'unknown'}`
    let storageValue: string | null = null
    let dismissed = false
    const allDismissKeys: Record<string, string> = {}
    try {
      storageValue = sessionStorage.getItem(storageKey)
      dismissed = storageValue === '1'
      // collect all version banner keys for debugging stale dismissals
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i)
        if (k && k.startsWith('versionBannerDismissed:')) {
          allDismissKeys[k] = sessionStorage.getItem(k) || ''
        }
      }
    } catch {
      // ignore storage errors (private mode, etc.)
    }
    const showBanner = mismatch && !dismissed
    return { mismatch, dismissed, showBanner, storageKey, storageValue, allDismissKeys }
  }

  const fetchStatusVersion = async (): Promise<{ version: string | null; service: string | null; error: string | null }> => {
    try {
      const res = await fetch('/status', {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
      })
      if (!res.ok) return { version: null, service: null, error: `HTTP ${res.status}` }
      const body = (await res.json()) as { version?: string; service?: string }
      return { version: body.version || null, service: body.service || null, error: null }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      return { version: null, service: null, error: msg }
    }
  }

  // Main helper — attached as global `version()`
  const version = async (opts?: { refresh?: boolean }) => {
    const clientVersion = getClientVersion()
    const ctx = getContextVersions()
    // server_version is authoritative; fall back to client_version field (both are _active_version)
    const serverVersion = ctx.server_version || ctx.client_version || null
    const banner = getBannerDebug(serverVersion)

    let status = await fetchStatusVersion()

    // Optionally refresh auth context and re-collect (helps when context is stale)
    if (opts?.refresh) {
      try {
        const { refreshContext } = useAuth()
        await refreshContext()
        const refreshed = getContextVersions()
        const refreshedServer = refreshed.server_version || refreshed.client_version || null
        // re-evaluate banner after refresh
        const refreshedBanner = getBannerDebug(refreshedServer)
        let refreshedStatus = status
        // also re-fetch status after refresh in case server just redeployed
        refreshedStatus = await fetchStatusVersion()
        const infoRefreshed = {
          clientVersion,
          serverVersion: refreshedServer,
          context: refreshed,
          banner: refreshedBanner,
          status: refreshedStatus,
          location: typeof window !== 'undefined' ? window.location.href : null,
          userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
          refreshed: true,
        }
        // eslint-disable-next-line no-console
        console.log(
          '%c[version] refreshed',
          'color:#4059D8;font-weight:700',
          infoRefreshed,
        )
        printHuman(clientVersion, refreshedServer, refreshedBanner, refreshed, refreshedStatus, true)
        return infoRefreshed
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[version] refresh failed', e)
      }
    }

    const info = {
      clientVersion,
      serverVersion,
      context: ctx,
      banner,
      status,
      location: typeof window !== 'undefined' ? window.location.href : null,
      userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
    }

    // Structured log for devtools
    // eslint-disable-next-line no-console
    console.log('%c[version]', 'color:#4059D8;font-weight:700', info)
    printHuman(clientVersion, serverVersion, banner, ctx, status, false)
    return info
  }

  function printHuman(
    clientVersion: string | null,
    serverVersion: string | null,
    banner: ReturnType<typeof getBannerDebug>,
    ctx: ReturnType<typeof getContextVersions>,
    status: Awaited<ReturnType<typeof fetchStatusVersion>>,
    refreshed: boolean,
  ) {
    const lines: string[] = []
    lines.push(`client (baked appVersion): ${clientVersion ?? 'unknown'}`)
    lines.push(`server (context):          ${serverVersion ?? 'unknown'} ${ctx.context_present ? '' : '(no auth context yet — try login, or check /status)'}`)
    if (ctx.server_version && ctx.client_version && ctx.server_version !== ctx.client_version) {
      lines.push(`  note: context server_version=${ctx.server_version} client_version=${ctx.client_version} (usually identical)`)
    }
    lines.push(`status (/status):          ${status.version ?? 'unknown'}${status.error ? ` (error: ${status.error})` : ''}`)
    lines.push(`mismatch (client ≠ server): ${banner.mismatch}`)
    lines.push(`showBanner:                ${banner.showBanner}  (mismatch && !dismissed)`)
    lines.push(`dismissed:                 ${banner.dismissed}  (sessionStorage ${banner.storageKey}=${banner.storageValue ?? 'null'})`)
    if (Object.keys(banner.allDismissKeys).length) {
      lines.push(`allDismissKeys:            ${JSON.stringify(banner.allDismissKeys)}`)
    }
    if (status.version && clientVersion && status.version !== clientVersion) {
      lines.push(`→ baked client ${clientVersion} ≠ status ${status.version}: you have a stale index.html (hard reload needed). Banner is expected.`)
    } else if (banner.mismatch) {
      lines.push(`→ mismatch detected: banner should be visible unless dismissed. Use version({refresh:true}) to re-check, or sessionStorage.removeItem('${banner.storageKey}') to un-dismiss.`)
    } else if (!serverVersion) {
      lines.push(`→ no serverVersion yet: log in and run version() again, or check Network → /ws/core/get-user-customer-context`)
    } else {
      lines.push(`→ versions match: banner should be hidden. If you still see "New Version Available", check for a stale service worker / HTTP cache. Try:  caches.keys().then(ks=>ks.forEach(k=>caches.delete(k))) then location.reload()`)
    }
    if (!refreshed) {
      lines.push(`hint: version({refresh:true}) will refresh auth context and re-fetch /status`)
    }
    // eslint-disable-next-line no-console
    console.log(lines.join('\n'))
  }

  // Expose globally — both window.version and globalThis.version
  try {
    const g = globalThis as unknown as Record<string, unknown>
    g.version = version
    // also expose a more explicit alias and the info helper for programmatic use
    g.__version = version
    g.versionInfo = version
    if (typeof window !== 'undefined') {
      ;(window as unknown as Record<string, unknown>).version = version
      ;(window as unknown as Record<string, unknown>).__version = version
      ;(window as unknown as Record<string, unknown>).versionInfo = version
    }
    // One-time hint (debug level so it doesn't clutter console)
    // eslint-disable-next-line no-console
    console.debug('[version] helper ready — type version() in devtools to check client/server versions')
  } catch {
    // ignore — console still works even if global assignment fails
  }
})
