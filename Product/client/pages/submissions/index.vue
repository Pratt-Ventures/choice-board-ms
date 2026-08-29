<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between ga-4 mb-6">
      <div>
        <div class="eyebrow">Account</div>
        <div class="page-title">My Reports</div>
        <div class="page-subtitle">
          Status of your bug reports and suggestions, most recent first.
        </div>
      </div>
      <v-btn variant="text" :loading="loading" @click="load">
        <i class="fa-solid fa-rotate mr-2" /> Refresh
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-3">
      <div class="text-subtitle-1 font-weight-bold font-display">Bug reports</div>
      <NuxtLink class="section-link" to="/submissions/new?type=bug">Create a Bug Report</NuxtLink>
    </div>
    <SubmissionStatusTable
      class="mb-8"
      kind="bug_report"
      :rows="bugs"
      :show-submitter="isAdmin"
    />

    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-3">
      <div class="text-subtitle-1 font-weight-bold font-display">Suggestions</div>
      <NuxtLink class="section-link" to="/submissions/new?type=suggestion">Create a Suggestion</NuxtLink>
    </div>
    <SubmissionStatusTable
      kind="suggestion"
      :rows="suggestions"
      :show-submitter="isAdmin"
    />
  </div>
</template>

<script setup lang="ts">
import type { UserCommunicationRow } from '~/types/api'

const api = useUserCommunicationApi()
const snackbar = useSnackbar()
const { isAdmin, userCommEnabled } = useAuth()

const loading = ref(false)
const suggestions = ref<UserCommunicationRow[]>([])
const bugs = ref<UserCommunicationRow[]>([])

onMounted(() => {
  if (!userCommEnabled.value) {
    navigateTo('/projects')
    return
  }
  load()
})

async function load() {
  loading.value = true
  try {
    const [bug, sug] = await Promise.all([
      api.retrieve('bug_report'),
      api.retrieve('suggestion'),
    ])
    if (bug.failure_reason) throw new Error(bug.failure_reason)
    if (sug.failure_reason) throw new Error(sug.failure_reason)
    bugs.value = bug.items || []
    suggestions.value = sug.items || []
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not load reports')
  }
  finally {
    loading.value = false
  }
}
</script>

<style scoped>
.section-link {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}
.section-link:hover {
  text-decoration: underline;
}
</style>
