<template>
  <v-app class="app-shell">
    <v-navigation-drawer
      v-model="drawer"
      :permanent="mdAndUp"
      :temporary="!mdAndUp"
      width="260"
      class="nav-drawer"
    >
      <div class="nav-brand">
        <div class="brand-badge">
          <i class="fa-solid fa-bolt" />
        </div>
        <div>
          <div class="brand-wordmark">Power Choice Pro</div>
          <span class="brand-tagline">Decision workspace</span>
        </div>
      </div>

      <div class="nav-section-label">Workspace</div>
      <v-list nav density="comfortable" class="py-0">
        <v-list-item
          v-for="item in workspaceNav"
          :key="item.to"
          :to="item.to"
          rounded="lg"
          active-class="nav-active"
        >
          <template #prepend>
            <i :class="['fa-icon', item.icon]" style="width:20px;margin-right:8px" />
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>

      <div class="nav-section-label">Account</div>
      <v-list nav density="comfortable" class="py-0">
        <v-list-item
          v-for="item in accountNav"
          :key="item.to"
          :to="item.to"
          rounded="lg"
          active-class="nav-active"
        >
          <template #prepend>
            <i :class="['fa-icon', item.icon]" style="width:20px;margin-right:8px" />
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>

      <div v-if="isSystemAdmin && userCommEnabled" class="nav-admin-block">
        <div class="nav-section-label">System Admin</div>
        <v-list nav density="comfortable" class="py-0">
          <v-list-item
            v-for="item in systemAdminNav"
            :key="item.to"
            :to="item.to"
            rounded="lg"
            active-class="nav-active"
          >
            <template #prepend>
              <i :class="['fa-icon', item.icon]" style="width:20px;margin-right:8px" />
            </template>
            <v-list-item-title>{{ item.title }}</v-list-item-title>
          </v-list-item>
        </v-list>
      </div>

      <template #append>
        <div class="pa-4">
          <v-card class="workspace-card" flat>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between mb-1">
                <span class="text-caption" style="opacity:.75;letter-spacing:.1em;font-weight:700">WORKSPACE</span>
                <i class="fa-solid fa-layer-group" style="opacity:.7" />
              </div>
              <div class="text-subtitle-1 font-weight-bold text-truncate" style="font-family:Manrope,Inter,sans-serif">
                {{ customerName || 'Workspace' }}
              </div>
              <div class="text-caption" style="opacity:.75">
                <template v-if="trialDays !== null">Trial · {{ trialDays }}d left</template>
                <template v-else>{{ userName || 'Signed in' }}</template>
              </div>
            </v-card-text>
          </v-card>
        </div>
      </template>
    </v-navigation-drawer>

    <v-app-bar flat height="68" color="surface" class="topbar">
      <v-app-bar-nav-icon v-if="!mdAndUp" @click="drawer = !drawer" />
      <div class="px-2" style="min-width:0">
        <div class="topbar-title text-truncate">{{ pageTitle }}</div>
        <div class="topbar-subtitle text-truncate">{{ pageSubtitle }}</div>
      </div>

      <v-spacer />

      <v-btn
        icon
        variant="text"
        aria-label="Toggle theme"
        @click="toggleTheme"
      >
        <i :class="isDark ? 'fa-solid fa-sun' : 'fa-solid fa-moon'" />
      </v-btn>

      <v-menu offset-y>
        <template #activator="{ props: menuProps }">
          <v-btn v-bind="menuProps" variant="text" rounded="lg" class="px-2 ml-1">
            <v-avatar size="33" color="primary">
              <span class="text-caption font-weight-bold text-white">{{ initials(userName) }}</span>
            </v-avatar>
            <span class="d-none d-sm-inline ml-2 font-weight-bold">{{ userName || 'Account' }}</span>
            <i class="fa-solid fa-chevron-down ml-2 d-none d-sm-inline" style="font-size:10px" />
          </v-btn>
        </template>
        <v-card min-width="280" class="pc-card" rounded="lg">
          <v-card-text class="pb-2">
            <div class="d-flex align-center ga-3">
              <v-avatar size="42" color="primary">
                <span class="text-body-2 font-weight-bold text-white">{{ initials(userName) }}</span>
              </v-avatar>
              <div style="min-width:0">
                <div class="text-body-2 font-weight-bold">{{ userName || 'User' }}</div>
                <div class="text-caption text-medium-emphasis text-truncate">{{ context?.email || '' }}</div>
              </div>
              <v-chip size="x-small" :color="isAdmin ? 'primary' : 'default'" variant="tonal" class="ml-auto">
                {{ isAdmin ? 'Admin' : 'Member' }}
              </v-chip>
            </div>
          </v-card-text>
          <v-list density="compact" class="py-0">
            <v-list-item title="Profile" to="/profile">
              <template #prepend><i class="fa-solid fa-user mr-3" style="width:18px;text-align:center" /></template>
            </v-list-item>
            <v-list-item title="Settings" to="/settings">
              <template #prepend><i class="fa-solid fa-gear mr-3" style="width:18px;text-align:center" /></template>
            </v-list-item>
            <v-list-item v-if="userCommEnabled" title="Submit Bug/Suggestion" to="/submissions/new">
              <template #prepend><i class="fa-solid fa-pen-to-square mr-3" style="width:18px;text-align:center" /></template>
            </v-list-item>
            <v-list-item v-if="userCommEnabled" title="My Reports" to="/submissions">
              <template #prepend><i class="fa-solid fa-clipboard-list mr-3" style="width:18px;text-align:center" /></template>
            </v-list-item>
            <v-list-item title="About" @click="aboutOpen = true">
              <template #prepend><i class="fa-solid fa-circle-info mr-3" style="width:18px;text-align:center" /></template>
            </v-list-item>
            <v-list-item title="Sign out" @click="logout">
              <template #prepend><i class="fa-solid fa-right-from-bracket mr-3" style="width:18px;text-align:center" /></template>
            </v-list-item>
          </v-list>
        </v-card>
      </v-menu>
    </v-app-bar>

    <v-main>
      <div class="page-container">
        <VersionBanner
          v-if="versionCheck.showBanner.value"
          :server-version="versionCheck.serverVersion.value"
          :client-version="versionCheck.clientVersion.value"
          @dismiss="versionCheck.dismiss()"
          @reload="versionCheck.reload()"
        />
        <v-alert
          v-if="!isAdmin"
          density="compact"
          variant="tonal"
          color="warning"
          class="mb-5"
        >
          <template #prepend><i class="fa-regular fa-eye" /></template>
          You're browsing with <b>read-only</b> access for project edits. You can still compare on projects you can open.
        </v-alert>
        <slot />
      </div>
    </v-main>

    <AboutDialog v-model="aboutOpen" />
    <AppSnackbar />
  </v-app>
</template>

<script setup lang="ts">
const route = useRoute()
const { userName, customerName, trialDays, isAdmin, isSystemAdmin, userCommEnabled, logout, context } = useAuth()
const { mdAndUp } = useDisplay()
const { initials } = useFormat()
const { isDark, toggle: toggleTheme } = useThemeMode()
const drawer = ref(true)
const aboutOpen = ref(false)
const versionCheck = useVersionCheck()

watch(mdAndUp, (value) => { drawer.value = value }, { immediate: true })

const workspaceNav = [
  { title: 'Projects', icon: 'fa-solid fa-folder-tree', to: '/projects' },
  { title: 'Sharing', icon: 'fa-solid fa-share-nodes', to: '/shares' },
  { title: 'Templates', icon: 'fa-solid fa-layer-group', to: '/templates' },
  { title: 'Team', icon: 'fa-solid fa-users', to: '/users' },
]

const accountNav = [
  { title: 'Profile', icon: 'fa-solid fa-user', to: '/profile' },
  { title: 'Settings', icon: 'fa-solid fa-gear', to: '/settings' },
]

const systemAdminNav = [
  { title: 'Review Bug Reports', icon: 'fa-solid fa-bug', to: '/admin/bugs' },
  { title: 'Review Suggestions', icon: 'fa-solid fa-lightbulb', to: '/admin/suggestions' },
]

const pageTitle = computed(() => {
  const projectRest = route.path.match(/^\/projects\/[^/]+(?:\/(.*))?$/)
  if (projectRest) {
    const rest = projectRest[1] || ''
    if (!rest) return 'Project - Overview'
    if (rest === 'edit') return 'Project - Edit Settings'
    return 'Project'
  }
  if (route.path.startsWith('/projects')) return 'Projects'
  if (route.path.startsWith('/shares')) return 'Sharing'
  if (route.path.startsWith('/templates')) return 'Templates'
  if (route.path.startsWith('/users')) return 'Team'
  if (route.path.startsWith('/submissions/new')) return 'Submit a report'
  if (route.path.startsWith('/submissions')) return 'My Reports'
  if (route.path.startsWith('/admin/suggestions')) return 'Review Suggestions'
  if (route.path.startsWith('/admin/bugs')) return 'Review Bug Reports'
  if (route.path.startsWith('/admin')) return 'System Admin'
  if (route.path.startsWith('/profile')) return 'Profile'
  if (route.path.startsWith('/settings')) return 'Settings'
  return 'Power Choice Pro'
})

const pageSubtitle = computed(() => {
  if (route.path.startsWith('/projects')) return 'Structure decisions and collect clear input'
  if (route.path.startsWith('/shares')) return 'Invitations and shared access'
  if (route.path.startsWith('/templates')) return 'Reusable decision factors'
  if (route.path.startsWith('/users')) return 'People in this workspace'
  if (route.path.startsWith('/submissions/new')) return 'Choose a type and tell us what you need'
  if (route.path.startsWith('/submissions')) return 'Status of your bug reports and suggestions'
  if (route.path.startsWith('/admin/suggestions')) return 'Incoming product suggestions'
  if (route.path.startsWith('/admin/bugs')) return 'Incoming bug reports'
  if (route.path.startsWith('/admin')) return 'System-wide inboxes'
  if (route.path.startsWith('/profile')) return 'Account details used in invitations and reports'
  if (route.path.startsWith('/settings')) return 'Defaults and advanced calculation controls'
  return 'Structured decisions, made clear'
})
</script>
