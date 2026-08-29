import { request, type APIRequestContext } from '@playwright/test'
import { randomBytes } from 'node:crypto'

export const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'
export const UI_BASE = process.env.E2E_UI_BASE || 'http://localhost:3000'

export type ShareAccessMode =
  | 'open_access'
  | 'email_any_unverified'
  | 'email_any_verified'
  | 'email_matching'
  | 'email_matching_verified'
  | 'recipient_email_verified'
  | 'password_only'
  | 'password_with_email_any_unverified'
  | 'password_with_email_any_verified'
  | 'password_with_email_matching'
  | 'password_with_email_matching_verified'
  | 'password_with_recipient_email_verified'

export const ALL_SHARE_ACCESS_MODES: ShareAccessMode[] = [
  'open_access',
  'email_any_unverified',
  'email_any_verified',
  'email_matching',
  'email_matching_verified',
  'recipient_email_verified',
  'password_only',
  'password_with_email_any_unverified',
  'password_with_email_any_verified',
  'password_with_email_matching',
  'password_with_email_matching_verified',
  'password_with_recipient_email_verified',
]

export function uid(prefix = 'e2e'): string {
  return `${prefix}-${randomBytes(6).toString('hex')}`
}

export type SeededShare = {
  mode: ShareAccessMode
  magicToken: string
  shareId: number
  recipientEmail: string
  password: string | null
  projectTitle: string
}

export type E2eSeed = {
  adminEmail: string
  adminPassword: string
  projectId: number
  projectTitle: string
  shares: Record<ShareAccessMode, SeededShare>
}

export async function createApiContext(): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: API_BASE,
    extraHTTPHeaders: { Accept: 'application/json' },
  })
}

async function assertOk(res: { ok: () => boolean; status: () => number; text: () => Promise<string> }, label: string) {
  if (!res.ok()) {
    throw new Error(`${label} failed (${res.status()}): ${await res.text()}`)
  }
}

export async function seedShareWorkspace(api: APIRequestContext): Promise<E2eSeed> {
  const adminEmail = `${uid('admin')}@example.com`
  const adminPassword = uid('pw')
  const projectTitle = `E2E Share Gates ${uid('proj')}`
  const projectTag = uid('tag')

  const created = await api.post('/ws/test-helper/create-activated-user', {
    data: {
      customer_name: `E2E Co ${uid()}`,
      admin_name: 'E2E Admin',
      admin_email: adminEmail,
      admin_phone: '555-0100',
      admin_password: adminPassword,
    },
  })
  await assertOk(created, 'create-activated-user')
  const createdBody = await created.json()
  if (!createdBody.customer_id) {
    throw new Error(`create-activated-user missing customer_id: ${JSON.stringify(createdBody)}`)
  }

  const login = await api.post('/auth-ws/login', {
    data: { email: adminEmail, password: adminPassword },
  })
  await assertOk(login, 'login')
  const state = await api.storageState()
  if (!state.cookies.some((c) => c.name === 'access_token')) {
    throw new Error('login did not set access_token cookie')
  }

  const projectRes = await api.post('/ws/custprojects/customer-project-create', {
    data: {
      project_tag: projectTag,
      project_title: projectTitle,
      project_description: 'E2E project for share access modes',
      min_expected_passes: 1,
      max_recommended_passes: 3,
    },
  })
  await assertOk(projectRes, 'customer-project-create')
  const projectBody = await projectRes.json()
  if (projectBody.failure_reason) {
    throw new Error(`project create failed: ${projectBody.failure_reason}`)
  }
  const projectId = projectBody.customer_project_info.id as number

  for (const title of ['Option Alpha', 'Option Beta']) {
    const alt = await api.post('/ws/custproject-content/alternative-create', {
      data: {
        project_id: projectId,
        alternative_title: title,
        alternative_description: `${title} description`,
      },
    })
    await assertOk(alt, `alternative-create ${title}`)
  }

  const factor = await api.post('/ws/custproject-content/factor-create', {
    data: {
      project_id: projectId,
      factor_title: 'Cost',
      factor_description: 'Relative cost',
      factor_polarity_positive: true,
    },
  })
  await assertOk(factor, 'factor-create')

  const shares = {} as Record<ShareAccessMode, SeededShare>
  for (const mode of ALL_SHARE_ACCESS_MODES) {
    const recipientEmail = `${uid('rcpt')}@example.com`
    const password = mode.startsWith('password') ? uid('spw') : null
    const body: Record<string, unknown> = {
      shared_type: 'vote',
      shared_entity_db_id: projectId,
      access_mode: mode,
      link_auto_send: false,
      share_link_name: `${mode} ${uid('lnk')}`,
      shared_with_person_name: 'E2E Recipient',
      shared_with_email: recipientEmail,
    }
    if (password) body.share_password = password

    const shareRes = await api.post('/ws/create-share-link', {
      data: body,
    })
    await assertOk(shareRes, `create-share-link ${mode}`)
    const shareBody = await shareRes.json()
    if (shareBody.failure_reason) {
      throw new Error(`share create ${mode} failed: ${shareBody.failure_reason}`)
    }
    const info = shareBody.link_info
    shares[mode] = {
      mode,
      magicToken: info.magic_token,
      shareId: info.id,
      recipientEmail,
      password,
      projectTitle,
    }
  }

  return {
    adminEmail,
    adminPassword,
    projectId,
    projectTitle,
    shares,
  }
}

export async function fetchLatestShareMagicKey(
  api: APIRequestContext,
  magicToken: string,
): Promise<string> {
  const res = await api.post('/ws/test-helper/get-latest-share-magic-key', {
    data: { magic_token: magicToken },
  })
  await assertOk(res, 'get-latest-share-magic-key')
  const body = await res.json()
  if (!body.access_magic_key) {
    throw new Error(`missing access_magic_key: ${JSON.stringify(body)}`)
  }
  return String(body.access_magic_key)
}
