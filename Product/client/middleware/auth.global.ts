export default defineNuxtRouteMiddleware(async (to) => {
  const publicPaths = new Set([
    '/login',
    '/signup',
    '/forgot-password',
    '/activate-customer',
  ])

  const isPublic
    = publicPaths.has(to.path)
      || to.path.startsWith('/forgot-password/')
      || to.path.startsWith('/activate-customer/')
      || to.path.startsWith('/signup/')
      || to.path.startsWith('/share/')

  const { ensureSession, isAuthenticated } = useAuth()

  if (import.meta.server) return

  await ensureSession()

  if (!isPublic && !isAuthenticated.value) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  }

  if (isAuthenticated.value && (to.path === '/login' || to.path === '/signup')) {
    return navigateTo('/projects')
  }

  if (isAuthenticated.value && to.path === '/') {
    return navigateTo('/projects')
  }
})
