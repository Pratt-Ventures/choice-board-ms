<template>
  <div>
    <div class="eyebrow">Account</div>
    <div class="page-title mb-2">Profile</div>
    <div class="page-subtitle mb-5">Information used in invitations and generated reports.</div>
    <v-card class="glass-card" max-width="640">
      <v-card-text class="pa-6">
        <div class="d-flex align-center ga-4 mb-6">
          <v-avatar size="64" color="primary">
            <span class="text-h6 text-white">{{ initials(userName) }}</span>
          </v-avatar>
          <div>
            <div class="text-h6 font-weight-bold">{{ userName }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ context?.email }}</div>
            <v-chip size="small" class="mt-2" variant="tonal" color="primary">
              {{ isAdmin ? 'Admin' : 'Member' }}
            </v-chip>
          </div>
        </div>
        <v-row dense>
          <v-col cols="12" md="6">
            <div class="text-caption text-medium-emphasis">Workspace</div>
            <div class="font-weight-medium">{{ customerName }}</div>
          </v-col>
          <v-col cols="12" md="6">
            <div class="text-caption text-medium-emphasis">Customer id</div>
            <div class="font-weight-medium mono">{{ context?.customer_id }}</div>
          </v-col>
          <v-col cols="12" md="6">
            <div class="text-caption text-medium-emphasis">Phone</div>
            <div class="font-weight-medium">{{ context?.user_record?.phone || '—' }}</div>
          </v-col>
          <v-col cols="12" md="6">
            <div class="text-caption text-medium-emphasis">Trial</div>
            <div class="font-weight-medium">{{ trialDays != null ? `${trialDays} days left` : '—' }}</div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card class="glass-card mt-5" max-width="640">
      <v-card-text class="pa-6">
        <div class="text-h6 font-weight-bold mb-1">Workspace branding</div>
        <div class="text-body-2 text-medium-emphasis mb-4">
          Optional company logo shown on shared Compare and Results pages (upload up to 8 MB; stored near 1 MB; PNG, JPEG, WebP, or GIF).
        </div>

        <div class="d-flex align-center ga-4 mb-4">
          <div class="branding-preview">
            <img v-if="previewUrl" :src="previewUrl" alt="Workspace branding" class="branding-preview__img" />
            <div v-else class="branding-preview__empty">
              <i class="fa-regular fa-image" />
            </div>
          </div>
          <div class="flex-grow-1">
            <div class="text-body-2 font-weight-medium">{{ customerName || 'Workspace' }}</div>
            <div class="text-caption text-medium-emphasis">
              {{ hasImage ? (meta?.original_file_name || meta?.file_name || 'Branding image on file') : 'No branding image uploaded' }}
            </div>
            <div v-if="meta?.byte_size" class="text-caption text-medium-emphasis">
              Stored {{ formatBytes(meta.byte_size) }}
              <template v-if="meta.original_byte_size && meta.original_byte_size !== meta.byte_size">
                · original {{ formatBytes(meta.original_byte_size) }}
              </template>
              <template v-if="meta.was_compressed"> · compressed for storage</template>
            </div>
          </div>
        </div>

        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
          class="d-none"
          @change="onFileSelected"
        />

        <div class="d-flex flex-wrap ga-2">
          <v-btn
            color="primary"
            variant="flat"
            :loading="uploading"
            :disabled="!isAdmin"
            @click="pickFile"
          >
            <i class="fa-solid fa-upload mr-2" />
            {{ hasImage ? 'Replace branding image' : 'Upload branding image' }}
          </v-btn>
          <v-btn
            v-if="hasImage"
            variant="tonal"
            color="error"
            :loading="deleting"
            :disabled="!isAdmin"
            @click="onDelete"
          >
            <i class="fa-solid fa-trash mr-2" />
            Delete
          </v-btn>
        </div>
        <div v-if="!isAdmin" class="text-caption text-medium-emphasis mt-3">
          Only workspace admins can change branding.
        </div>
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-4">{{ error }}</v-alert>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import type { BrandingImageResult } from '~/types/api'

const { context, userName, customerName, isAdmin, trialDays } = useAuth()
const { initials } = useFormat()
const brandingApi = useBrandingApi()
const snackbar = useSnackbar()

const meta = ref<BrandingImageResult | null>(null)
const previewUrl = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const deleting = ref(false)
const error = ref('')

const hasImage = computed(() => !!meta.value?.has_image)

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

async function loadMeta() {
  error.value = ''
  try {
    const res = await brandingApi.customerMeta()
    meta.value = res
    if (res.has_image) {
      previewUrl.value = brandingApi.customerImageUrl(res.modify_date || Date.now())
    }
    else {
      previewUrl.value = ''
    }
  }
  catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load branding'
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFileSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 8 * 1_048_576) {
    error.value = 'Image must be 8 MB or smaller'
    return
  }
  uploading.value = true
  error.value = ''
  try {
    const res = await brandingApi.uploadCustomerImage(file)
    if (res.failure_reason) {
      error.value = res.failure_reason
      return
    }
    meta.value = res
    previewUrl.value = brandingApi.customerImageUrl(res.modify_date || Date.now())
    snackbar.success('Branding image saved')
  }
  catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Upload failed'
  }
  finally {
    uploading.value = false
  }
}

async function onDelete() {
  deleting.value = true
  error.value = ''
  try {
    const res = await brandingApi.deleteCustomerImage()
    if (res.failure_reason) {
      error.value = res.failure_reason
      return
    }
    meta.value = { has_image: false }
    previewUrl.value = ''
    snackbar.success('Branding image removed')
  }
  catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Delete failed'
  }
  finally {
    deleting.value = false
  }
}

onMounted(loadMeta)
</script>

<style scoped>
.branding-preview {
  width: 88px;
  height: 88px;
  border-radius: 16px;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-surface-variant), 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}
.branding-preview__img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.branding-preview__empty {
  color: rgba(var(--v-theme-on-surface), 0.35);
  font-size: 1.5rem;
}
</style>
