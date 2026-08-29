export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'pc-theme-mode'

const mode = ref<ThemeMode>('light')
let hydrated = false

function readStored(): ThemeMode {
  if (!import.meta.client) return 'light'
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return 'light'
}

function applyDom(next: ThemeMode) {
  if (!import.meta.client) return
  document.documentElement.dataset.theme = next
  document.documentElement.style.colorScheme = next
  localStorage.setItem(STORAGE_KEY, next)
}

export function useThemeMode() {
  const theme = useTheme()

  function setMode(next: ThemeMode) {
    mode.value = next
    theme.change(next)
    applyDom(next)
  }

  function toggle() {
    setMode(mode.value === 'dark' ? 'light' : 'dark')
  }

  if (import.meta.client && !hydrated) {
    hydrated = true
    const stored = readStored()
    mode.value = stored
    theme.change(stored)
    applyDom(stored)
  }

  const isDark = computed(() => mode.value === 'dark')

  return {
    mode,
    isDark,
    setMode,
    toggle,
  }
}
