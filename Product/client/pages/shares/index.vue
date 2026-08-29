<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between ga-4 mb-6">
      <div>
        <div class="eyebrow">Workspace</div>
        <div class="page-title">Sharing</div>
        <div class="page-subtitle">
          Overview of invite links across projects — expand a project for share rows, then open history for security and access detail.
        </div>
      </div>
      <v-btn variant="text" :loading="loading" @click="load">
        <i class="fa-solid fa-rotate mr-2" /> Refresh
      </v-btn>
    </div>

    <v-row class="mb-5" dense>
      <v-col v-for="m in summaryMetrics" :key="m.label" cols="6" md="3">
        <v-card class="glass-card">
          <v-card-text>
            <div class="text-caption text-medium-emphasis">{{ m.label }}</div>
            <div class="text-h4 font-weight-bold mt-1">{{ m.value }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <div class="d-flex flex-wrap ga-3 mb-4 align-center">
      <v-text-field
        v-model="search"
        placeholder="Search projects or recipients"
        prepend-inner-icon="mdi-magnify"
        hide-details
        density="compact"
        style="max-width:360px"
        clearable
      />
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <div v-if="!loading && !filteredProjects.length" class="empty-state py-16">
      <i class="fa-solid fa-share-nodes fa-3x mb-4" style="color:var(--pc-primary)" />
      <div class="text-h6 font-weight-bold">No share links yet</div>
      <div class="text-body-2 mt-2 mb-4">Create invite links from a project’s Sharing page.</div>
      <v-btn color="primary" to="/projects">Go to projects</v-btn>
    </div>

    <div v-else class="d-flex flex-column ga-4">
      <v-card
        v-for="row in filteredProjects"
        :key="row.projectId"
        class="glass-card share-surface-card"
        rounded="md"
      >
        <v-card-text class="pa-5">
          <div class="d-flex flex-wrap justify-space-between ga-3 align-start">
            <div>
              <div class="text-h6 font-weight-bold">{{ row.title }}</div>
              <div class="text-caption mono text-medium-emphasis">{{ row.tag }}</div>
              <div class="d-flex flex-wrap ga-2 mt-3">
                <div class="metric-pill"><strong>{{ row.shares.length }}</strong><span>Shares</span></div>
                <div class="metric-pill"><strong>{{ row.activeCount }}</strong><span>Active</span></div>
                <div class="metric-pill"><strong>{{ row.sessionTotal }}</strong><span>Sessions</span></div>
                <div class="metric-pill"><strong>{{ row.voteTotal }}</strong><span>Comparisons</span></div>
              </div>
            </div>
            <div class="d-flex flex-wrap ga-2">
              <v-btn size="small" variant="tonal" color="primary" @click="toggleExpand(row.projectId)">
                <i class="fa-solid fa-table mr-2" />
                {{ expanded[row.projectId] ? 'Hide shares' : 'Show shares' }}
              </v-btn>
              <v-btn size="small" variant="text" :to="`/projects/${row.projectId}/shares`">
                Manage
              </v-btn>
              <v-btn size="small" variant="text" color="primary" :to="`/projects/${row.projectId}/shares?invite=1`">
                Invite people
              </v-btn>
            </div>
          </div>

          <v-expand-transition>
            <div v-if="expanded[row.projectId]" class="mt-4">
              <v-table density="compact" class="data-table">
                <thead>
                  <tr>
                    <th>Share</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Sessions</th>
                    <th>Comparisons</th>
                    <th>Magic</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="entry in row.shares" :key="entry.share_id">
                    <td>
                      <div class="font-weight-medium">{{ entry.share_link?.share_link_name || 'Share link' }}</div>
                      <div class="text-caption text-medium-emphasis">
                        {{ entry.share_link?.shared_with_person_name || '—' }}
                        <span v-if="entry.share_link?.shared_with_email"> · {{ entry.share_link.shared_with_email }}</span>
                      </div>
                    </td>
                    <td>
                      <v-chip size="x-small" :color="typeColor(entry.share_link?.shared_type)" variant="flat">
                        {{ typeLabel(entry.share_link?.shared_type) }}
                      </v-chip>
                    </td>
                    <td>
                      <v-chip
                        size="x-small"
                        :color="entry.share_link?.share_link_enabled ? 'success' : 'error'"
                        variant="tonal"
                      >
                        {{ entry.share_link?.share_link_enabled ? 'Active' : 'Disabled' }}
                      </v-chip>
                    </td>
                    <td>{{ entry.session_count ?? entry.share_link_accesses?.length ?? 0 }}</td>
                    <td>{{ entry.observation_count ?? 0 }}</td>
                    <td>
                      {{ entry.magic_keys_used ?? 0 }}/{{ entry.magic_keys_issued ?? entry.share_link_magic_keys?.length ?? 0 }}
                    </td>
                    <td class="text-right">
                      <div class="d-flex flex-column align-end">
                        <v-btn size="small" variant="text" color="primary" @click="openDetail(entry, row)">
                          History
                        </v-btn>
                        <v-btn
                          size="small"
                          variant="text"
                          @click="copyLink(entry.share_link_url || '')"
                        >
                          Copy link
                        </v-btn>
                        <v-btn
                          v-if="canSendInvite(entry)"
                          size="small"
                          variant="text"
                          color="primary"
                          :loading="sendingInviteId === entry.share_id"
                          @click="sendOrResendInvite(entry)"
                        >
                          {{ entry.invite_email_sent ? 'Resend invite' : 'Send invite' }}
                        </v-btn>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </v-table>
              <div v-if="!row.shares.length" class="text-medium-emphasis pa-3">No shares on this project.</div>
            </div>
          </v-expand-transition>
        </v-card-text>
      </v-card>
    </div>

    <v-dialog v-model="detailOpen" max-width="720" scrollable>
      <v-card v-if="detailEntry" class="pc-dialog-card share-history-dialog">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Share details</span>
          <v-btn icon variant="text" size="small" @click="detailOpen = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="share-history-body px-6 pt-2">
          <div class="text-h6 font-weight-bold mb-1">
            {{ detailEntry.share_link?.share_link_name || 'Share link' }}
          </div>
          <div class="text-caption text-medium-emphasis mb-4">
            Project: {{ detailProjectTitle }}
            <span v-if="detailEntry.share_link?.shared_with_email">
              · To: {{ detailEntry.share_link.shared_with_person_name || detailEntry.share_link.shared_with_email }}
              <span v-if="detailEntry.share_link.shared_with_person_name"> ({{ detailEntry.share_link.shared_with_email }})</span>
            </span>
          </div>

          <div class="d-flex flex-wrap ga-2 mb-4">
            <v-chip size="small" :color="typeColor(detailEntry.share_link?.shared_type)" variant="flat">
              {{ typeLabel(detailEntry.share_link?.shared_type) }}
            </v-chip>
            <v-chip
              size="small"
              :color="detailEntry.share_link?.share_link_enabled ? 'success' : 'error'"
              variant="tonal"
            >
              {{ detailEntry.share_link?.share_link_enabled ? 'Active' : 'Disabled' }}
            </v-chip>
            <v-chip size="small" variant="tonal">{{ modeLabel(detailEntry.share_link?.access_mode) }}</v-chip>
          </div>

          <v-row dense class="mb-4">
            <v-col cols="12" md="6">
              <div class="text-caption text-medium-emphasis">Security</div>
              <div class="text-body-2">
                Access mode: <strong>{{ modeLabel(detailEntry.share_link?.access_mode) }}</strong>
              </div>
              <div class="text-body-2">
                Password:
                <strong>{{ detailEntry.password_set ? 'Set (masked)' : 'Not set' }}</strong>
              </div>
              <div class="text-body-2">
                Password in email:
                <strong>{{ detailEntry.share_link?.share_password_in_email ? 'Yes' : 'No' }}</strong>
              </div>
              <div class="text-body-2">
                Magic token:
                <strong>{{ detailEntry.share_link?.magic_token ? 'Generated' : '—' }}</strong>
                <span v-if="detailEntry.share_link?.magic_token" class="text-caption mono ml-1">
                  …{{ String(detailEntry.share_link.magic_token).slice(-6) }}
                </span>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="text-caption text-medium-emphasis">Activity</div>
              <div class="text-body-2">Sessions: <strong>{{ detailEntry.session_count ?? 0 }}</strong></div>
              <div class="text-body-2">Total hits: <strong>{{ detailEntry.total_hits ?? 0 }}</strong></div>
              <div class="text-body-2">
                Magic keys: <strong>{{ detailEntry.magic_keys_used ?? 0 }}</strong> used /
                <strong>{{ detailEntry.magic_keys_issued ?? 0 }}</strong> issued
              </div>
              <div class="text-body-2">
                Participants: <strong>{{ detailEntry.participant_count ?? 0 }}</strong>
              </div>
              <div class="text-body-2">
                Comparisons: <strong>{{ detailEntry.observation_count ?? 0 }}</strong>
              </div>
              <div class="text-body-2">
                Expiration:
                <strong>
                  {{ detailEntry.share_link_expired
                    ? 'Expired'
                    : detailEntry.share_link?.share_link_expiration === -1
                      ? 'No limit'
                      : `${detailEntry.share_link?.share_link_expiration ?? '—'} days from create` }}
                </strong>
              </div>
              <div class="text-body-2">
                Invite email:
                <strong>
                  {{ detailEntry.invite_email_sent
                    ? (detailEntry.invite_email_last_sent
                      ? `Sent ${formatDate(detailEntry.invite_email_last_sent, true)}`
                      : 'Sent')
                    : 'Not sent' }}
                </strong>
              </div>
            </v-col>
          </v-row>

          <div class="text-caption mono mb-4" style="word-break:break-all">
            {{ detailEntry.share_link_url }}
          </div>

          <div class="text-subtitle-2 font-weight-bold mb-2">Access history</div>
          <v-table v-if="(detailEntry.share_link_accesses || []).length" density="compact">
            <thead>
              <tr><th>Viewer</th><th>Email</th><th>Opens</th><th>Last</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in detailEntry.share_link_accesses" :key="a.id">
                <td>{{ a.captured_display_name || '—' }}</td>
                <td>{{ a.captured_email || '—' }}</td>
                <td>{{ a.access_count }}</td>
                <td>{{ formatDate(a.modify_date || a.create_date, true) }}</td>
              </tr>
            </tbody>
          </v-table>
          <div v-else class="text-medium-emphasis mb-4">No access sessions yet.</div>

          <div class="text-subtitle-2 font-weight-bold mb-2 mt-4">Magic key history</div>
          <v-table v-if="(detailEntry.share_link_magic_keys || []).length" density="compact">
            <thead>
              <tr><th>Email</th><th>Name</th><th>Issued</th><th>Used</th></tr>
            </thead>
            <tbody>
              <tr v-for="k in detailEntry.share_link_magic_keys" :key="k.id">
                <td>{{ k.captured_email || '—' }}</td>
                <td>{{ k.captured_display_name || '—' }}</td>
                <td>{{ formatDate(k.create_date, true) }}</td>
                <td>{{ k.accessed_date ? formatDate(k.accessed_date, true) : 'Not used' }}</td>
              </tr>
            </tbody>
          </v-table>
          <div v-else class="text-medium-emphasis">No magic keys issued.</div>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-btn
            v-if="detailEntry.project_id > 0"
            variant="text"
            :to="`/projects/${detailEntry.project_id}/shares`"
          >
            Open project sharing
          </v-btn>
          <v-spacer />
          <v-btn
            v-if="canSendInvite(detailEntry)"
            variant="flat"
            color="primary"
            :loading="sendingInviteId === detailEntry.share_id"
            @click="sendOrResendInvite(detailEntry)"
          >
            <i class="fa-regular fa-envelope mr-2" />
            {{ detailEntry.invite_email_sent ? 'Resend invite' : 'Send invite' }}
          </v-btn>
          <v-btn variant="tonal" color="primary" @click="copyLink(detailEntry.share_link_url || '')">
            Copy invite link
          </v-btn>
          <v-btn variant="text" @click="detailOpen = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type { CustomerProject, ShareLinkAuthsAccesses } from '~/types/api'

const projectsApi = useProjectsApi()
const sharesApi = useSharesApi()
const snackbar = useSnackbar()
const { formatDate, copyText } = useFormat()
const { requireAdmin } = useAuth()

const loading = ref(true)
const search = ref('')
const expanded = ref<Record<number, boolean>>({})
const projectMap = ref<Record<number, CustomerProject>>({})
const sharesByProject = ref<Record<number, ShareLinkAuthsAccesses[]>>({})

const detailOpen = ref(false)
const detailEntry = ref<ShareLinkAuthsAccesses | null>(null)
const detailProjectTitle = ref('')
const sendingInviteId = ref<number | null>(null)

const accessModes = [
  { title: 'Open access', value: 'open_access' },
  { title: 'Any email (unverified)', value: 'email_any_unverified' },
  { title: 'Any email (verified magic link)', value: 'email_any_verified' },
  { title: 'Matching email only', value: 'email_matching' },
  { title: 'Matching email + verified', value: 'email_matching_verified' },
  { title: 'Recipient email verified', value: 'recipient_email_verified' },
  { title: 'Password only', value: 'password_only' },
  { title: 'Password + any email', value: 'password_with_email_any_unverified' },
  { title: 'Password + verified email', value: 'password_with_email_any_verified' },
  { title: 'Password + matching email', value: 'password_with_email_matching' },
  { title: 'Password + matching verified', value: 'password_with_email_matching_verified' },
  { title: 'Password + recipient verified', value: 'password_with_recipient_email_verified' },
]

type ProjectShareRow = {
  projectId: number
  title: string
  tag: string
  shares: ShareLinkAuthsAccesses[]
  activeCount: number
  sessionTotal: number
  voteTotal: number
}

const projectRows = computed<ProjectShareRow[]>(() => {
  const ids = new Set<number>([
    ...Object.keys(projectMap.value).map(Number),
    ...Object.keys(sharesByProject.value).map(Number),
  ])
  return [...ids]
    .filter(id => (sharesByProject.value[id] || []).length > 0 || projectMap.value[id])
    .map((projectId) => {
      const p = projectMap.value[projectId]
      const shares = sharesByProject.value[projectId] || []
      return {
        projectId,
        title: p?.project_title || p?.project_tag || `Project ${projectId}`,
        tag: p?.project_tag || '',
        shares,
        activeCount: shares.filter(s => s.share_link?.share_link_enabled).length,
        sessionTotal: shares.reduce((n, s) => n + (s.session_count ?? s.share_link_accesses?.length ?? 0), 0),
        voteTotal: shares.reduce((n, s) => n + (s.observation_count ?? 0), 0),
      }
    })
    .filter(r => r.shares.length > 0)
    .sort((a, b) => a.title.localeCompare(b.title))
})

const filteredProjects = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return projectRows.value
  return projectRows.value.filter((row) => {
    if (row.title.toLowerCase().includes(q) || row.tag.toLowerCase().includes(q)) return true
    return row.shares.some((s) => {
      const link = s.share_link
      return (
        (link?.share_link_name || '').toLowerCase().includes(q)
        || (link?.shared_with_person_name || '').toLowerCase().includes(q)
        || (link?.shared_with_email || '').toLowerCase().includes(q)
        || (link?.shared_with_company_name || '').toLowerCase().includes(q)
      )
    })
  })
})

const summaryMetrics = computed(() => {
  const all = projectRows.value.flatMap(r => r.shares)
  return [
    { label: 'Projects with shares', value: projectRows.value.length },
    { label: 'Share links', value: all.length },
    { label: 'Active links', value: all.filter(s => s.share_link?.share_link_enabled).length },
    { label: 'Sessions', value: all.reduce((n, s) => n + (s.session_count ?? 0), 0) },
  ]
})

function typeLabel(t?: string) {
  if (t === 'vote') return 'Compare Only'
  if (t === 'vote_view') return 'Compare and See Only Your Results'
  if (t === 'report') return 'See Full Results'
  return t || 'Share'
}

function typeColor(t?: string) {
  if (t === 'vote') return 'primary'
  if (t === 'vote_view') return 'secondary'
  if (t === 'report') return 'success'
  return 'default'
}

function modeLabel(m?: string) {
  return accessModes.find(a => a.value === m)?.title || m || '—'
}

function toggleExpand(projectId: number) {
  expanded.value = { ...expanded.value, [projectId]: !expanded.value[projectId] }
}

function openDetail(entry: ShareLinkAuthsAccesses, row: ProjectShareRow) {
  detailEntry.value = entry
  detailProjectTitle.value = row.title
  detailOpen.value = true
}

function copyLink(url: string) {
  if (url) copyText(url, 'Share link')
}

function canSendInvite(entry: ShareLinkAuthsAccesses | null) {
  const link = entry?.share_link
  if (!link?.shared_with_email) return false
  if (!link.share_link_enabled) return false
  if (entry?.share_link_expired) return false
  return true
}

async function sendOrResendInvite(entry: ShareLinkAuthsAccesses) {
  if (!canSendInvite(entry) || !requireAdmin()) return
  sendingInviteId.value = entry.share_id
  try {
    const res = await sharesApi.sendInvitation({ share_id: entry.share_id })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success(res.was_resend ? 'Invitation resent' : 'Invitation sent')
    entry.invite_email_sent = true
    await load()
    const refreshed = (sharesByProject.value[entry.project_id] || []).find(s => s.share_id === entry.share_id)
    if (refreshed) detailEntry.value = refreshed
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not send invitation')
  }
  finally {
    sendingInviteId.value = null
  }
}

async function load() {
  loading.value = true
  try {
    const result = await projectsApi.listProjectsSummary()
    if (result.failure_reason) throw new Error(result.failure_reason)
    const map: Record<number, CustomerProject> = {}
    const ids: number[] = []
    for (const item of result.projects || []) {
      if (item.project?.id != null) {
        map[item.project.id] = item.project
        ids.push(item.project.id)
      }
    }
    projectMap.value = map

    const activity = await sharesApi.activityForProjects(ids.length ? ids : [-1])
    const byProject: Record<number, ShareLinkAuthsAccesses[]> = {}
    if (!activity.failure_reason || activity.share_info_list_per_project_id) {
      const raw = activity.share_info_list_per_project_id || {}
      for (const [key, list] of Object.entries(raw)) {
        byProject[Number(key)] = list || []
      }
    }
    sharesByProject.value = byProject
  }
  catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Failed to load sharing'
    if (String(msg).includes('No matching')) {
      sharesByProject.value = {}
    }
    else {
      snackbar.error(msg)
    }
  }
  finally {
    loading.value = false
  }
}

onMounted(load)
</script>
