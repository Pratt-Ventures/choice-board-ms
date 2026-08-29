/**
 * Analytic Tracking injection plugin — lightweight client-side middleware.
 *
 * Fetches effective payload once per browser session (sessionStorage) from
 * unauthenticated endpoint GET /api/_public/analytic-tracking (primary) and
 * injects it into <head> and preserves the same script element across renders.
 *
 * Contract:
 * - 204 or empty => no injection (sentinel __EMPTY__ cached to avoid refetch)
 * - 200 text/html with <script>...</script> => substituted, whitelisted payload
 * - Idempotent: a connected script is never removed or executed again
 * - Self-healing: the script is restored if removed or if <head> is replaced
 * - Timing: after document.head exists, on initial load + SPA navigations + MutationObserver fallback
 */

const STORAGE_KEY = 'analyticTracking:payload:v1'
const SENTINEL_EMPTY = '__EMPTY__'
const SCRIPT_ID = 'analytic-tracking-script'
const ENDPOINT_PRIMARY = '/api/_public/analytic-tracking'
const ENDPOINT_FALLBACK = '/auth-ws/_public/analytic-tracking'

let memoryCache: string | null = null
let fetchPromise: Promise<string | null> | null = null

function safeGetStorage(): string | null {
  try {
    if (typeof window === 'undefined' || !window.sessionStorage) return memoryCache
    return window.sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return memoryCache
  }
}

function safeSetStorage(value: string): void {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      window.sessionStorage.setItem(STORAGE_KEY, value)
    } else {
      memoryCache = value
    }
  } catch {
    memoryCache = value
  }
  if (memoryCache !== null && value !== SENTINEL_EMPTY) {
    // keep memory in sync when sessionStorage available
    memoryCache = value
  } else if (value === SENTINEL_EMPTY) {
    memoryCache = SENTINEL_EMPTY
  }
}

function getCachedPayload(): string | null {
  const raw = safeGetStorage()
  if (raw === null) return null
  if (raw === SENTINEL_EMPTY) return SENTINEL_EMPTY
  return raw
}

function hasConnectedTrackingScript(): boolean {
  if (typeof document === 'undefined' || !document.head) return false
  const existing = document.getElementById(SCRIPT_ID)
  return !!existing && existing.isConnected && existing.parentElement === document.head
}

function injectHeadScript(payload: string | null): void {
  if (!payload || payload === SENTINEL_EMPTY || !payload.trim()) return
  if (typeof document === 'undefined' || !document.head) return

  // Dynamically inserted scripts execute when appended. Never remove/recreate a
  // connected tracker merely because another integration added a later head
  // child; doing so executes the tracker again and can create a mutation loop.
  if (hasConnectedTrackingScript()) return

  const existing = document.getElementById(SCRIPT_ID)
  if (existing) existing.remove()

  const trimmed = payload.trim()
  if (!trimmed) return

  // Parse using temporary container
  const temp = document.createElement('div')
  temp.innerHTML = trimmed
  const scriptNodes = temp.querySelectorAll('script')

  if (scriptNodes.length === 0) {
    // Fallback: if payload is not wrapped in <script>, treat whole payload as script string?
    // Create a script element with payload as text? But spec says payload is <SCRIPT> tag, so no-op.
    return
  }

  scriptNodes.forEach((node, idx) => {
    const s = document.createElement('script')
    // Copy all attributes from source node
    for (const attr of Array.from(node.attributes)) {
      s.setAttribute(attr.name, attr.value)
    }
    // Only first script gets the sentinel id (ensures exactly one tracked element)
    if (idx === 0) s.id = SCRIPT_ID
    // Ensure empty contents handling: copy textContent (should be empty per spec)
    s.textContent = node.textContent || ''
    // If multiple scripts are configured, append them in payload order.
    document.head.appendChild(s)
  })
}

async function fetchPayload(): Promise<string | null> {
  const tryFetch = async (url: string): Promise<Response> => {
    return fetch(url, {
      method: 'GET',
      credentials: 'omit',
      headers: { Accept: 'text/html, text/plain, */*' },
    })
  }

  try {
    let response = await tryFetch(ENDPOINT_PRIMARY)
    // Fallback to alias if primary 404 (e.g., mount mismatch)
    if (response.status === 404) {
      try {
        response = await tryFetch(ENDPOINT_FALLBACK)
      } catch {
        // keep primary response
      }
    }

    if (response.status === 204) {
      safeSetStorage(SENTINEL_EMPTY)
      return SENTINEL_EMPTY
    }
    if (!response.ok) {
      safeSetStorage(SENTINEL_EMPTY)
      return SENTINEL_EMPTY
    }
    const text = (await response.text()).trim()
    if (!text) {
      safeSetStorage(SENTINEL_EMPTY)
      return SENTINEL_EMPTY
    }
    safeSetStorage(text)
    return text
  } catch {
    safeSetStorage(SENTINEL_EMPTY)
    return SENTINEL_EMPTY
  }
}

async function ensurePayloadAndInject(): Promise<void> {
  const cached = getCachedPayload()
  if (cached !== null) {
    if (cached !== SENTINEL_EMPTY) injectHeadScript(cached)
    return
  }

  if (!fetchPromise) {
    fetchPromise = fetchPayload()
  }
  const payload = await fetchPromise
  if (payload && payload !== SENTINEL_EMPTY) {
    // Ensure head exists before injecting; if not yet, wait for DOMContentLoaded
    if (typeof document !== 'undefined' && document.head) {
      injectHeadScript(payload)
    } else if (typeof document !== 'undefined') {
      document.addEventListener('DOMContentLoaded', () => injectHeadScript(payload), { once: true })
    }
  }
}

function scheduleInjectFromCache(): void {
  const cached = getCachedPayload()
  if (cached && cached !== SENTINEL_EMPTY) {
    if (typeof document !== 'undefined' && document.head) {
      injectHeadScript(cached)
    } else if (typeof document !== 'undefined') {
      document.addEventListener('DOMContentLoaded', () => {
        const c = getCachedPayload()
        if (c && c !== SENTINEL_EMPTY) injectHeadScript(c)
      }, { once: true })
    }
  }
}

export default defineNuxtPlugin(() => {
  if (import.meta.server) return

  // Initial fetch/inject after head is available
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        void ensurePayloadAndInject()
      }, { once: true })
    } else {
      void ensurePayloadAndInject()
    }

    // Also attempt immediate if cached and head already exists (covers SPA hydration)
    scheduleInjectFromCache()
  }

  // SPA navigation: re-apply on route change (idempotent)
  try {
    const router = useRouter()
    router.afterEach(() => {
      scheduleInjectFromCache()
      // If cache miss (rare, first navigation before fetch resolved), trigger fetch
      const cached = getCachedPayload()
      if (cached === null) void ensurePayloadAndInject()
    })
  } catch {
    // useRouter not available in some contexts
  }

  // MutationObserver fallbacks: restore a genuinely removed script or recover
  // after head replacement. Other head mutations must not re-execute analytics.
  if (typeof window !== 'undefined' && typeof MutationObserver !== 'undefined') {
    const observeHead = () => {
      if (!document.head) return
      const headObserver = new MutationObserver(() => {
        const cached = getCachedPayload()
        if (cached && cached !== SENTINEL_EMPTY) {
          if (!hasConnectedTrackingScript()) injectHeadScript(cached)
        }
      })
      headObserver.observe(document.head, { childList: true })

      // Observe documentElement for head replacement (e.g., full head swap)
      const docObserver = new MutationObserver((mutations) => {
        for (const m of mutations) {
          for (const node of Array.from(m.addedNodes)) {
            if ((node as Element).tagName === 'HEAD') {
              const cached = getCachedPayload()
              if (cached && cached !== SENTINEL_EMPTY) injectHeadScript(cached)
              // re-attach head observer to new head
              try { headObserver.disconnect() } catch {}
              if (document.head) headObserver.observe(document.head, { childList: true })
            }
          }
        }
      })
      if (document.documentElement) {
        docObserver.observe(document.documentElement, { childList: true })
      }
    }

    if (document.head) {
      observeHead()
    } else {
      document.addEventListener('DOMContentLoaded', observeHead, { once: true })
    }
  }
})
