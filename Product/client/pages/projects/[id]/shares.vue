<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between ga-3 mb-5">
      <div>
        <div class="eyebrow">Sharing</div>
        <div class="page-title">{{ project?.project_title || 'Project shares' }}</div>
        <div class="page-subtitle">
          Issue links for external comparisons, personal ranking views, or full results access. Monitor access and revoke anytime.
        </div>
        <div v-if="remainingTimeCopy" class="text-body-2 text-medium-emphasis mt-2">{{ remainingTimeCopy }}</div>
      </div>
      <v-btn color="primary" variant="flat" @click="openCreate">
        <i class="fa-solid fa-link mr-2" /> New share link
      </v-btn>
    </div>

    <v-row dense class="mb-5">
      <v-col cols="6" md="3" v-for="m in summary" :key="m.label">
        <v-card class="glass-card">
          <v-card-text>
            <div class="text-caption text-medium-emphasis">{{ m.label }}</div>
            <div class="text-h4 font-weight-bold">{{ m.value }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <div v-if="!loading && !shares.length" class="empty-state py-12">
      <i class="fa-solid fa-share-nodes fa-3x mb-3" style="color:var(--pc-primary)" />
      <div class="font-weight-bold">No share links yet</div>
      <div class="text-body-2 mt-2">Create a Compare Only, Compare and See Only Your Results, or See Full Results link with the access mode you need.</div>
    </div>

    <v-row v-else>
      <v-col v-for="entry in shares" :key="entry.share_id" cols="12">
        <v-card class="glass-card share-surface-card" rounded="md">
          <v-card-text class="pa-5">
            <div class="d-flex flex-wrap justify-space-between ga-3">
              <div>
                <div class="d-flex flex-wrap ga-2 mb-2">
                  <v-chip size="small" :color="typeColor(entry.share_link?.shared_type)" variant="flat">
                    {{ typeLabel(entry.share_link?.shared_type) }}
                  </v-chip>
                  <v-chip size="small" :color="entry.share_link?.share_link_enabled ? 'success' : 'error'" variant="tonal">
                    {{ entry.share_link?.share_link_enabled ? 'Active' : 'Disabled' }}
                  </v-chip>
                  <v-chip size="small" variant="tonal">{{ modeLabel(entry.share_link?.access_mode) }}</v-chip>
                </div>
                <div class="text-h6 font-weight-bold">{{ entry.share_link?.share_link_name || 'Share link' }}</div>
                <div class="text-caption text-medium-emphasis mt-1">
                  To: {{ entry.share_link?.shared_with_person_name || '—' }}
                  <span v-if="entry.share_link?.shared_with_email"> · {{ entry.share_link.shared_with_email }}</span>
                  <span v-if="entry.share_link?.shared_with_company_name"> · {{ entry.share_link.shared_with_company_name }}</span>
                </div>
                <div class="text-caption mono mt-2" style="word-break:break-all">{{ entry.share_link_url }}</div>
              </div>
              <div class="d-flex flex-wrap ga-2 align-start">
                <v-btn size="small" variant="tonal" color="primary" @click="copyLink(entry.share_link_url || '')">
                  <i class="fa-regular fa-copy mr-2" /> Copy link only
                </v-btn>
                <v-btn size="small" variant="tonal" color="secondary" @click="copyInviteText(inviteForEntry(entry))">
                  <i class="fa-regular fa-envelope mr-2" /> Copy text
                </v-btn>
                <v-btn size="small" variant="text" @click="previewInvite(inviteForEntry(entry))">
                  Preview
                </v-btn>
                <v-btn
                  size="small"
                  variant="text"
                  :color="entry.share_link?.share_link_enabled ? 'error' : 'success'"
                  @click="toggle(entry)"
                >
                  {{ entry.share_link?.share_link_enabled ? 'Disable' : 'Enable' }}
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
                <v-btn size="small" variant="text" @click="extend(entry)">Extend +30d</v-btn>
              </div>
            </div>

            <v-divider class="my-4" />

            <v-row dense>
              <v-col cols="6" md="3">
                <div class="text-caption text-medium-emphasis">Sessions</div>
                <div class="text-h5 font-weight-bold">{{ entry.session_count ?? entry.share_link_accesses?.length ?? 0 }}</div>
                <div class="text-caption">Opens: {{ entry.total_hits ?? (entry.share_link_accesses || []).reduce((s, a) => s + (a.access_count || 0), 0) }}</div>
              </v-col>
              <v-col cols="6" md="3">
                <div class="text-caption text-medium-emphasis">Comparisons</div>
                <div class="text-h5 font-weight-bold">{{ entry.observation_count ?? 0 }}</div>
                <div class="text-caption">Participants: {{ entry.participant_count ?? 0 }}</div>
              </v-col>
              <v-col cols="6" md="3">
                <div class="text-caption text-medium-emphasis">Magic keys</div>
                <div class="text-h5 font-weight-bold">{{ entry.magic_keys_issued ?? entry.share_link_magic_keys?.length ?? 0 }}</div>
                <div class="text-caption">Used: {{ entry.magic_keys_used ?? (entry.share_link_magic_keys || []).filter(k => k.accessed_date).length }}</div>
              </v-col>
              <v-col cols="6" md="3">
                <div class="text-caption text-medium-emphasis">Security</div>
                <div class="text-body-2 font-weight-bold">{{ modeLabel(entry.share_link?.access_mode) }}</div>
                <div class="text-caption">
                  Password: {{ entry.password_set ? 'Set (masked)' : 'Not set' }}
                  · Token: {{ entry.share_link?.magic_token ? 'Generated' : '—' }}
                </div>
              </v-col>
            </v-row>

            <div class="d-flex flex-wrap ga-2 mt-3">
              <v-btn size="small" variant="tonal" @click="openHistory(entry)">
                <i class="fa-solid fa-clock-rotate-left mr-2" /> Detailed history
              </v-btn>
            </div>

            <v-expansion-panels v-if="(entry.share_link_accesses || []).length" class="mt-3" variant="accordion">
              <v-expansion-panel rounded="md">
                <v-expansion-panel-title>Access log (first look)</v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-table density="compact">
                    <thead>
                      <tr><th>Viewer</th><th>Email</th><th>Opens</th><th>Last</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="a in entry.share_link_accesses" :key="a.id">
                        <td>{{ a.captured_display_name || '—' }}</td>
                        <td>{{ a.captured_email || '—' }}</td>
                        <td>{{ a.access_count }}</td>
                        <td>{{ formatDate(a.modify_date || a.create_date, true) }}</td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <div v-if="!loading && shares.length" class="d-flex justify-end mt-5">
      <v-btn color="primary" variant="flat" @click="openCreate">
        <i class="fa-solid fa-link mr-2" /> New share link
      </v-btn>
    </div>

    <v-dialog v-model="createDialog" max-width="640">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Create share link</span>
          <v-btn icon variant="text" size="small" @click="createDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <v-row>
            <v-col cols="12">
              <div class="text-subtitle-2 mb-2">Share type</div>
              <v-btn-toggle v-model="createForm.shared_type" mandatory color="primary" divided class="flex-wrap">
                <v-btn value="vote">Compare Only</v-btn>
                <v-btn value="vote_view">Compare and See Only Your Results</v-btn>
                <v-btn value="report">See Full Results</v-btn>
              </v-btn-toggle>
              <div class="text-caption text-medium-emphasis mt-2">{{ typeHelp }}</div>
            </v-col>
            <v-col cols="12">
              <div class="access-mode-row d-flex align-center flex-wrap ga-3">
                <v-select
                  v-model="createForm.access_mode"
                  class="access-mode-select"
                  :items="displayedAccessModes"
                  item-title="title"
                  item-value="value"
                  label="Access mode"
                  hide-details
                />
                <button
                  v-if="!showAllAccessModes && hasExtraAccessModes"
                  type="button"
                  class="access-mode-toggle"
                  @click="showAllAccessModes = true"
                >show all*</button>
                <button
                  v-if="showAllAccessModes"
                  type="button"
                  class="access-mode-toggle"
                  @click="showCommonAccessModes"
                >show basic</button>
              </div>
              <div v-if="accessModeHelp" class="text-caption text-medium-emphasis mt-1">{{ accessModeHelp }}</div>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="createForm.shared_with_person_name" label="Recipient name" />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="createForm.shared_with_company_name" label="Organization" />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="createForm.shared_with_email"
                label="Recipient email"
                type="email"
                :required="needsRecipientEmail"
              />
              <div v-if="needsRecipientEmail" class="text-caption text-medium-emphasis mt-1">
                Required for this access mode.
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="createForm.share_link_name" label="Link display name" />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model.number="createForm.share_link_expiration" type="number" label="Expiration (days, -1 unlimited)" />
            </v-col>
            <v-col cols="12" md="6" v-if="needsPassword">
              <v-text-field v-model="createForm.share_password" label="Share password" type="password" required />
            </v-col>
            <v-col cols="12" md="6">
              <v-switch v-model="createForm.link_auto_send" label="Email link to recipient" />
            </v-col>
            <v-col cols="12" md="6" v-if="needsPassword">
              <v-switch v-model="createForm.share_password_in_email" label="Include password in email" />
            </v-col>
          </v-row>
          <v-alert v-if="lastCreatedUrl" type="success" variant="tonal" class="mt-2">
            {{ lastCreatedSuccessMessage }}
            <div class="mono text-caption mt-1" style="word-break:break-all">{{ lastCreatedUrl }}</div>
            <div class="d-flex flex-wrap ga-2 mt-3">
              <v-btn size="small" variant="tonal" color="primary" @click="copyLink(lastCreatedUrl)">
                <i class="fa-regular fa-copy mr-2" /> Copy link only
              </v-btn>
              <v-btn
                size="small"
                variant="tonal"
                color="secondary"
                :disabled="!lastCreatedInvite"
                @click="copyInviteText(lastCreatedInvite)"
              >
                <i class="fa-regular fa-envelope mr-2" /> Copy text
              </v-btn>
              <v-btn
                size="small"
                variant="text"
                :disabled="!lastCreatedInvite"
                @click="previewInvite(lastCreatedInvite)"
              >
                Preview
              </v-btn>
            </div>
            <div v-if="lastCreatedInvite" class="invite-preview mt-3 pa-3">
              <div class="text-caption text-medium-emphasis mb-1">Invitation preview</div>
              <div class="invite-preview-body" v-html="lastCreatedInvite.html" />
            </div>
          </v-alert>
          <div v-if="shareCreated" class="d-flex align-center ga-2 text-success text-body-2 mt-3">
            <i class="fa-solid fa-circle-check" />
            Share successfully created
          </div>
          <div v-if="linkEmailSent" class="d-flex align-center ga-2 text-success text-body-2 mt-1">
            <i class="fa-solid fa-envelope-circle-check" />
            Email sent to {{ createForm.shared_with_email || 'the recipient' }}
          </div>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="createDialog = false">Close</v-btn>
          <v-btn color="primary" variant="flat" :loading="creating" :disabled="shareCreated || !createForm.access_mode" @click="create">Create</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="previewDialog" max-width="560">
      <v-card class="pc-dialog-card" v-if="previewPayload">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Invitation preview</span>
          <v-btn icon variant="text" size="small" @click="previewDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <div class="text-caption text-medium-emphasis mb-2">Formatted (HTML paste)</div>
          <div class="invite-preview pa-4 mb-4">
            <div class="invite-preview-body" v-html="previewPayload.html" />
          </div>
          <div class="text-caption text-medium-emphasis mb-2">Plain text</div>
          <pre class="invite-plain">{{ previewPayload.plain }}</pre>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="previewDialog = false">Close</v-btn>
          <v-btn size="small" variant="tonal" color="primary" @click="copyLink(previewPayload.url)">
            Copy link only
          </v-btn>
          <v-btn size="small" variant="flat" color="secondary" @click="copyInviteText(previewPayload)">
            Copy text
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="historyDialog" max-width="720" scrollable>
      <v-card v-if="historyEntry" class="pc-dialog-card share-history-dialog">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Share history</span>
          <v-btn icon variant="text" size="small" @click="historyDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="share-history-body px-6 pt-2">
          <div class="text-h6 font-weight-bold mb-2">{{ historyEntry.share_link?.share_link_name || 'Share link' }}</div>
          <v-row dense class="mb-4">
            <v-col cols="12" md="6">
              <div class="text-caption text-medium-emphasis">Security</div>
              <div class="text-body-2">Mode: <strong>{{ modeLabel(historyEntry.share_link?.access_mode) }}</strong></div>
              <div class="text-body-2">Password: <strong>{{ historyEntry.password_set ? 'Set (masked)' : 'Not set' }}</strong></div>
              <div class="text-body-2">
                Magic token:
                <strong>{{ historyEntry.share_link?.magic_token ? 'Generated' : '—' }}</strong>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="text-caption text-medium-emphasis">Activity</div>
              <div class="text-body-2">Sessions: <strong>{{ historyEntry.session_count ?? 0 }}</strong></div>
              <div class="text-body-2">Comparisons: <strong>{{ historyEntry.observation_count ?? 0 }}</strong></div>
              <div class="text-body-2">Participants: <strong>{{ historyEntry.participant_count ?? 0 }}</strong></div>
              <div class="text-body-2">
                Magic: <strong>{{ historyEntry.magic_keys_used ?? 0 }}</strong> /
                <strong>{{ historyEntry.magic_keys_issued ?? 0 }}</strong>
              </div>
              <div class="text-body-2">
                Invite email:
                <strong>
                  {{ historyEntry.invite_email_sent
                    ? (historyEntry.invite_email_last_sent
                      ? `Sent ${formatDate(historyEntry.invite_email_last_sent, true)}`
                      : 'Sent')
                    : 'Not sent' }}
                </strong>
              </div>
            </v-col>
          </v-row>
          <div class="text-subtitle-2 font-weight-bold mb-2">Access history</div>
          <v-table v-if="(historyEntry.share_link_accesses || []).length" density="compact" class="mb-4">
            <thead>
              <tr><th>Viewer</th><th>Email</th><th>Opens</th><th>Last</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in historyEntry.share_link_accesses" :key="a.id">
                <td>{{ a.captured_display_name || '—' }}</td>
                <td>{{ a.captured_email || '—' }}</td>
                <td>{{ a.access_count }}</td>
                <td>{{ formatDate(a.modify_date || a.create_date, true) }}</td>
              </tr>
            </tbody>
          </v-table>
          <div v-else class="text-medium-emphasis mb-4">No access sessions yet.</div>
          <div class="text-subtitle-2 font-weight-bold mb-2">Magic key history</div>
          <v-table v-if="(historyEntry.share_link_magic_keys || []).length" density="compact">
            <thead>
              <tr><th>Email</th><th>Name</th><th>Issued</th><th>Used</th></tr>
            </thead>
            <tbody>
              <tr v-for="k in historyEntry.share_link_magic_keys" :key="k.id">
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
          <v-spacer />
          <v-btn
            v-if="canSendInvite(historyEntry)"
            variant="flat"
            color="primary"
            :loading="sendingInviteId === historyEntry.share_id"
            @click="sendOrResendInvite(historyEntry)"
          >
            <i class="fa-regular fa-envelope mr-2" />
            {{ historyEntry.invite_email_sent ? 'Resend invite' : 'Send invite' }}
          </v-btn>
          <v-btn variant="text" @click="historyDialog = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.access-mode-select {
  max-width: 22rem;
  flex: 0 1 22rem;
}
.access-mode-toggle {
  appearance: none;
  background: none;
  border: 0;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font: inherit;
  font-size: 0.75rem;
  line-height: 1.25;
  letter-spacing: 0.01em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-decoration: underline;
  text-underline-offset: 0.18em;
  white-space: nowrap;
}
.access-mode-toggle:hover,
.access-mode-toggle:focus-visible {
  color: rgb(var(--v-theme-primary));
}
.invite-preview {
  background: rgba(var(--v-theme-surface-variant), 0.35);
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.invite-preview-body :deep(p) {
  margin: 0 0 0.65em;
  line-height: 1.45;
}
.invite-preview-body :deep(p:last-child) {
  margin-bottom: 0;
}
.invite-preview-body :deep(a) {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
  text-decoration: underline;
}
.invite-plain {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.45;
  margin: 0;
  padding: 12px;
  border-radius: 12px;
  background: rgba(var(--v-theme-surface-variant), 0.35);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>

<script setup lang="ts">
import type { CustomerProject, ShareLinkAuthsAccesses } from '~/types/api'
import type { ShareAccessMode, ShareType } from '~/composables/useSharesApi'
import { projectRemainingTimeCopy } from '~/utils/projectEndTime'

const route = useRoute()
const projectsApi = useProjectsApi()
const sharesApi = useSharesApi()
const snackbar = useSnackbar()
const { formatDate, copyText, copyRich } = useFormat()
const { requireAdmin } = useAuth()

type InvitePayload = {
  url: string
  plain: string
  html: string
  anchor: string
}

const project = ref<CustomerProject | null>(null)
const remainingTimeCopy = computed(() => projectRemainingTimeCopy(project.value?.end_time))
const shares = ref<ShareLinkAuthsAccesses[]>([])
const loading = ref(true)
const createDialog = ref(false)
const creating = ref(false)
const shareCreated = ref(false)
const linkEmailSent = ref(false)
const lastCreatedUrl = ref('')
const lastCreatedCopied = ref(false)
const lastCreatedInvite = ref<InvitePayload | null>(null)
const previewDialog = ref(false)
const previewPayload = ref<InvitePayload | null>(null)
const historyDialog = ref(false)
const historyEntry = ref<ShareLinkAuthsAccesses | null>(null)
const sendingInviteId = ref<number | null>(null)
const lastCreatedSuccessMessage = computed(() =>
  lastCreatedCopied.value
    ? 'Link created - link copied to clipboard'
    : 'Link created',
)

const createForm = reactive({
  shared_type: 'vote_view' as ShareType,
  access_mode: 'email_any_unverified' as ShareAccessMode | '',
  shared_with_person_name: '',
  shared_with_company_name: '',
  shared_with_email: '',
  share_link_name: '',
  share_link_expiration: 14,
  share_password: '',
  share_password_in_email: false,
  link_auto_send: false,
})

const accessModes = [
  { title: 'Open access', value: 'open_access', flag: 'enable_share_open_access' },
  { title: 'Any email (unverified)', value: 'email_any_unverified', flag: 'enable_share_email_any_unverified' },
  { title: 'Any email (verified magic link)', value: 'email_any_verified', flag: 'enable_share_email_any_verified' },
  { title: 'Matching email only', value: 'email_matching', flag: 'enable_share_email_matching' },
  { title: 'Matching email + verified', value: 'email_matching_verified', flag: 'enable_share_email_matching_verified' },
  { title: 'Recipient email verified', value: 'recipient_email_verified', flag: 'enable_share_recipient_email_verified' },
  { title: 'Password only', value: 'password_only', flag: 'enable_share_password_only' },
  { title: 'Password + any email', value: 'password_with_email_any_unverified', flag: 'enable_share_password_with_email_any_unverified' },
  { title: 'Password + verified email', value: 'password_with_email_any_verified', flag: 'enable_share_password_with_email_any_verified' },
  { title: 'Password + matching email', value: 'password_with_email_matching', flag: 'enable_share_password_with_email_matching' },
  { title: 'Password + matching verified', value: 'password_with_email_matching_verified', flag: 'enable_share_password_with_email_matching_verified' },
  { title: 'Password + recipient verified', value: 'password_with_recipient_email_verified', flag: 'enable_share_password_with_recipient_email_verified' },
]

const accessModeNotes: Record<string, string> = {
  open_access: 'Access Url; Access granted (no input required); Name optional.',
  email_any_unverified: 'Access Url; Enter Name & Any Email (not verified); Access Granted.',
  email_any_verified: 'Access Url; Enter Name & Any Email; Token email sent; Follow link or enter key from token email; Access Granted.',
  email_matching: 'Access Url; Enter Name & Email; Email must match share; Access Granted.',
  email_matching_verified: 'Access Url; Enter Name & Email; Email must match share; Token email sent; Use link or key to verify; Access Granted.',
  recipient_email_verified: 'Access Url; Enter Name Only; key goes to the email on file; Use link or key to verify; Access Granted.',
  password_only: 'Access Url; Enter Name Only; Password required from share; Access Granted.',
  password_with_email_any_unverified: 'Access Url; Enter Name & Any Email (not verified); Password required from share; Access Granted.',
  password_with_email_any_verified: 'Access Url; Enter Name & Any Email (verified); Password required from share; Token email sent; Use link or key to verify; Access Granted.',
  password_with_email_matching: 'Access Url; Enter Name & Email; Email must match share; Password required from share; Access Granted.',
  password_with_email_matching_verified: 'Access Url; Enter Name & Email; Email must match share; Password required from share; Token email sent; Use link or key to verify; Access Granted.',
  password_with_recipient_email_verified: 'Access Url; Enter Name Only; Password required from share; key goes to the email on file; Use link or key to verify; Access Granted.',
}

const { context } = useAuth()
const showAllAccessModes = ref(false)
const availableAccessModes = computed(() => {
  const settings = context.value?.settings as Record<string, unknown> | undefined
  if (!settings) return []
  return accessModes.filter(m => {
    const enabled = settings[m.flag]
    return typeof enabled !== 'boolean' ? true : enabled
  })
})
const configuredAccessModeValues = computed(() => new Set(availableAccessModes.value.map(m => m.value)))
const hasExtraAccessModes = computed(() =>
  accessModes.some(m => !configuredAccessModeValues.value.has(m.value)),
)
const displayedAccessModes = computed(() => {
  const source = showAllAccessModes.value ? accessModes : availableAccessModes.value
  return source.map(m => ({
    title: showAllAccessModes.value && !configuredAccessModeValues.value.has(m.value)
      ? `${m.title}*`
      : m.title,
    value: m.value,
  }))
})

function firstEnabledAccessMode(): ShareAccessMode {
  return (availableAccessModes.value[0]?.value || 'email_any_unverified') as ShareAccessMode
}

function showCommonAccessModes() {
  showAllAccessModes.value = false
  if (!configuredAccessModeValues.value.has(createForm.access_mode)) {
    createForm.access_mode = ''
  }
}

const accessModeHelp = computed(() => accessModeNotes[createForm.access_mode] || '')

const needsPassword = computed(() => String(createForm.access_mode).startsWith('password'))
const needsRecipientEmail = computed(() => {
  if (createForm.link_auto_send) return true
  return /matching|recipient/.test(String(createForm.access_mode))
})
const typeHelp = computed(() => {
  if (createForm.shared_type === 'vote') return 'Recipient can run comparisons and submit their input.'
  if (createForm.shared_type === 'vote_view') return 'Recipient compares and can view their personal ranking after mark complete (not group outcomes).'
  return 'Recipient sees full results: rankings, participants, and agreement detail.'
})

const summary = computed(() => {
  const active = shares.value.filter(s => s.share_link?.share_link_enabled).length
  const accesses = shares.value.reduce((n, s) => n + (s.share_link_accesses?.length || 0), 0)
  const votes = shares.value.filter(s => s.share_link?.shared_type === 'vote').length
  const reports = shares.value.filter(s => s.share_link?.shared_type === 'report').length
  return [
    { label: 'Links', value: shares.value.length },
    { label: 'Active', value: active },
    { label: 'Unique access rows', value: accesses },
    { label: 'Compare Only / See Full Results', value: `${votes} / ${reports}` },
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

async function load() {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const p = await projectsApi.getProject(id)
    if (p.failure_reason || !p.customer_project_info) throw new Error(p.failure_reason || 'Project not found')
    project.value = p.customer_project_info
    const activity = await sharesApi.activityForProject(id)
    shares.value = activity.share_info_list || []
  }
  catch (e: unknown) {
    // empty activity returns failure_reason — treat as empty
    if (e instanceof Error && e.message.includes('No matching')) shares.value = []
    else snackbar.error(e instanceof Error ? e.message : 'Failed to load shares')
  }
  finally {
    loading.value = false
  }
}

function projectDisplayName() {
  return project.value?.project_title || project.value?.project_tag || 'Decision project'
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function buildInvite(opts: {
  url: string
  sharedType?: string | null
  personName?: string | null
  companyName?: string | null
  email?: string | null
  linkName?: string | null
  projectName?: string | null
}): InvitePayload | null {
  const url = (opts.url || '').trim()
  if (!url) return null
  const projectName = (opts.projectName || opts.linkName || 'Decision project').trim() || 'Decision project'
  const person = (opts.personName || '').trim()
  const company = (opts.companyName || '').trim()
  const email = (opts.email || '').trim()
  const type = opts.sharedType || 'vote'
  const remaining = projectRemainingTimeCopy(project.value?.end_time)
  const anchor = `Add your voice to decision project - ${projectName}`
  const greeting = person ? `Hi ${person},` : 'Hello,'
  let purpose = `You're invited to add your voice to the decision project "${projectName}".`
  if (type === 'vote_view') {
    purpose = `You're invited to view your voting status for the decision project "${projectName}".`
  }
  else if (type === 'report') {
    purpose = `You're invited to view the full report for the decision project "${projectName}".`
  }
  const metaLines: string[] = []
  if (company) metaLines.push(`Organization: ${company}`)
  if (email) metaLines.push(`Email: ${email}`)
  if (opts.linkName && opts.linkName.trim() && opts.linkName.trim() !== projectName) {
    metaLines.push(`Share: ${opts.linkName.trim()}`)
  }

  const plainParts = [greeting, '', purpose, '']
  if (remaining) plainParts.push(remaining, '')
  plainParts.push(anchor, url)
  if (metaLines.length) plainParts.push('', ...metaLines)
  const plain = plainParts.join('\n')

  const htmlParts = [
    `<p>${escapeHtml(greeting)}</p>`,
    `<p>${escapeHtml(purpose)}</p>`,
  ]
  if (remaining) htmlParts.push(`<p>${escapeHtml(remaining)}</p>`)
  htmlParts.push(`<p><a href="${escapeHtml(url)}">${escapeHtml(anchor)}</a></p>`)
  if (metaLines.length) {
    htmlParts.push(`<p>${metaLines.map(escapeHtml).join('<br/>')}</p>`)
  }
  const html = htmlParts.join('')

  return { url, plain, html, anchor }
}

function inviteForEntry(entry: ShareLinkAuthsAccesses): InvitePayload | null {
  const link = entry.share_link
  return buildInvite({
    url: entry.share_link_url || '',
    sharedType: link?.shared_type,
    personName: link?.shared_with_person_name,
    companyName: link?.shared_with_company_name,
    email: link?.shared_with_email,
    linkName: link?.share_link_name,
    projectName: projectDisplayName(),
  })
}

function resetCreateForm() {
  showAllAccessModes.value = false
  createForm.shared_type = 'vote_view'
  createForm.access_mode = firstEnabledAccessMode()
  createForm.shared_with_person_name = ''
  createForm.shared_with_company_name = ''
  createForm.shared_with_email = ''
  createForm.share_link_name = ''
  createForm.share_link_expiration = 14
  createForm.share_password = ''
  createForm.share_password_in_email = false
  createForm.link_auto_send = false
}

watch(availableAccessModes, (modes) => {
  if (showAllAccessModes.value) return
  if (!modes.length || !createForm.access_mode) return
  if (!modes.some(m => m.value === createForm.access_mode)) {
    createForm.access_mode = firstEnabledAccessMode()
  }
})

function isRecipientEmailVerifiedMode(mode: string) {
  return mode === 'recipient_email_verified' || mode === 'password_with_recipient_email_verified'
}

watch(() => createForm.access_mode, (mode) => {
  createForm.link_auto_send = isRecipientEmailVerifiedMode(mode)
})

watch(createForm, () => {
  shareCreated.value = false
  linkEmailSent.value = false
}, { deep: true })

function openCreate() {
  if (!requireAdmin()) return
  lastCreatedUrl.value = ''
  lastCreatedCopied.value = false
  lastCreatedInvite.value = null
  shareCreated.value = false
  linkEmailSent.value = false
  resetCreateForm()
  createForm.share_link_name = project.value?.project_title || project.value?.project_tag || ''
  createDialog.value = true
}

function maybeOpenInviteFromQuery() {
  const raw = route.query.invite
  const flag = Array.isArray(raw) ? raw[0] : raw
  if (flag === '1' || flag === 'true') {
    openCreate()
    const q = { ...route.query }
    delete q.invite
    navigateTo({ path: route.path, query: q }, { replace: true })
  }
}

async function create() {
  if (!project.value) return
  if (!createForm.access_mode) {
    snackbar.error('Select an access mode')
    return
  }
  if (needsRecipientEmail.value && !String(createForm.shared_with_email || '').trim()) {
    snackbar.error('Recipient email is required for this access mode')
    return
  }
  if (needsPassword.value && !String(createForm.share_password || '').trim()) {
    snackbar.error('Share password is required for this access mode')
    return
  }
  creating.value = true
  try {
    const res = await sharesApi.createShareLink({
      shared_type: createForm.shared_type,
      shared_entity_db_id: project.value.id,
      access_mode: createForm.access_mode,
      shared_with_person_name: createForm.shared_with_person_name || null,
      shared_with_company_name: createForm.shared_with_company_name || null,
      shared_with_email: createForm.shared_with_email || null,
      share_link_name: createForm.share_link_name || null,
      share_link_expiration: createForm.share_link_expiration,
      share_password: createForm.share_password || null,
      share_password_in_email: createForm.share_password_in_email,
      link_auto_send: createForm.link_auto_send,
    })
    if (res.failure_reason && !res.link_info) throw new Error(res.failure_reason)
    shareCreated.value = true
    linkEmailSent.value = res.link_email_sent === true
    lastCreatedUrl.value = res.link_url || ''
    lastCreatedCopied.value = false
    lastCreatedInvite.value = buildInvite({
      url: lastCreatedUrl.value,
      sharedType: createForm.shared_type,
      personName: createForm.shared_with_person_name,
      companyName: createForm.shared_with_company_name,
      email: createForm.shared_with_email,
      linkName: createForm.share_link_name,
      projectName: projectDisplayName(),
    })
    if (lastCreatedUrl.value && !linkEmailSent.value) {
      lastCreatedCopied.value = await copyTextQuiet(lastCreatedUrl.value)
    }
    if (res.failure_reason) snackbar.info(res.failure_reason)
    else if (lastCreatedCopied.value) snackbar.success('Share link created - link copied to clipboard')
    else snackbar.success('Share link created')
    await load()
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Create failed')
  }
  finally {
    creating.value = false
  }
}

async function toggle(entry: ShareLinkAuthsAccesses) {
  if (!requireAdmin()) return
  const enabled = !entry.share_link?.share_link_enabled
  const res = await sharesApi.extendOrDisable({
    share_id: entry.share_id,
    share_link_enabled: enabled,
  })
  if (res.failure_reason) snackbar.error(res.failure_reason)
  else {
    snackbar.success(enabled ? 'Link enabled' : 'Link disabled')
    await load()
  }
}

async function extend(entry: ShareLinkAuthsAccesses) {
  if (!requireAdmin()) return
  const current = entry.share_link?.share_link_expiration ?? 14
  const next = current < 0 ? 30 : current + 30
  const res = await sharesApi.extendOrDisable({ share_id: entry.share_id, share_link_expiration: next })
  if (res.failure_reason) snackbar.error(res.failure_reason)
  else {
    snackbar.success('Expiration extended')
    await load()
  }
}

async function copyTextQuiet(value: string) {
  try {
    await navigator.clipboard.writeText(value)
    return true
  }
  catch {
    return false
  }
}

function copyLink(url: string) {
  if (url) copyText(url, 'Share link')
}

function copyInviteText(invite: InvitePayload | null) {
  if (!invite) {
    snackbar.error('Nothing to copy')
    return
  }
  copyRich(invite.plain, invite.html, 'Invitation text')
}

function previewInvite(invite: InvitePayload | null) {
  if (!invite) {
    snackbar.error('Nothing to preview')
    return
  }
  previewPayload.value = invite
  previewDialog.value = true
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
    const refreshed = shares.value.find(s => s.share_id === entry.share_id)
    if (refreshed && historyEntry.value?.share_id === entry.share_id) {
      historyEntry.value = refreshed
    }
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not send invitation')
  }
  finally {
    sendingInviteId.value = null
  }
}

function openHistory(entry: ShareLinkAuthsAccesses) {
  historyEntry.value = entry
  historyDialog.value = true
}

onMounted(async () => {
  await load()
  maybeOpenInviteFromQuery()
})
</script>
