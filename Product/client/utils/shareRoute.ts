export function shareMagicKeyFromRoute(route: {
  query: Record<string, unknown>
  params: Record<string, unknown>
}): string {
  const pick = (value: unknown) => {
    if (typeof value === 'string' && value) return value
    if (Array.isArray(value) && typeof value[0] === 'string' && value[0]) return value[0]
    return ''
  }
  return pick(route.query.key) || pick(route.params.key)
}
