/** Shared unlock flag so share layout can load branding images after gate auth. */
export function useShareSession() {
  const unlocked = useState<boolean>('share-session-unlocked', () => false)
  const token = useState<string>('share-session-token', () => '')

  function markUnlocked(shareToken: string) {
    token.value = shareToken
    unlocked.value = true
  }

  function reset() {
    unlocked.value = false
    token.value = ''
  }

  return { unlocked, token, markUnlocked, reset }
}
