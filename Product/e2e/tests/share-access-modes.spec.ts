import { test, expect } from '@playwright/test'
import {
  ALL_SHARE_ACCESS_MODES,
  createApiContext,
  fetchLatestShareMagicKey,
  seedShareWorkspace,
  type E2eSeed,
  type SeededShare,
  type ShareAccessMode,
  uid,
} from '../helpers/api'
import {
  clickAlreadyHaveCode,
  completeVerifiedUnlock,
  expectEmailFieldCount,
  expectEnterCodeView,
  expectGateMessage,
  expectGateVisible,
  expectOnFileEmailHint,
  gateRoot,
  expectSendCodeView,
  expectUnlockedCompare,
  openShareVote,
  openShareVotePathKey,
  openShareVoteWithKey,
  submitGate,
} from '../helpers/gate'

let seed: E2eSeed

test.beforeAll(async () => {
  const api = await createApiContext()
  try {
    seed = await seedShareWorkspace(api)
  } finally {
    await api.dispose()
  }
})

test.describe.configure({ mode: 'serial' })

function share(mode: ShareAccessMode): SeededShare {
  return seed.shares[mode]
}

async function withApi<T>(fn: (api: Awaited<ReturnType<typeof createApiContext>>) => Promise<T>): Promise<T> {
  const api = await createApiContext()
  try {
    return await fn(api)
  } finally {
    await api.dispose()
  }
}

test('catalog covers every defined share security mode', () => {
  expect(ALL_SHARE_ACCESS_MODES).toHaveLength(12)
  for (const mode of ALL_SHARE_ACCESS_MODES) {
    expect(seed.shares[mode]?.magicToken).toBeTruthy()
  }
})

test('open_access unlocks without credentials (optional name on probe)', async ({ page }) => {
  const s = share('open_access')
  await openShareVote(page, s.magicToken)
  // Probe on mount grants open access immediately.
  await expectUnlockedCompare(page, s.projectTitle)
})

test('email_any_unverified requires name + any email', async ({ page }) => {
  const s = share('email_any_unverified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)

  await submitGate(page, { name: 'Guest Any' })
  await expectGateMessage(page, /email/i)

  await submitGate(page, {
    name: 'Guest Any',
    email: `${uid('any')}@example.com`,
  })
  await expectUnlockedCompare(page, s.projectTitle)
})

test('email_matching requires the recipient email only', async ({ page }) => {
  const s = share('email_matching')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)

  await submitGate(page, {
    name: 'Match Guest',
    email: 'wrong@example.com',
  })
  await expectGateMessage(page, /match|email/i)

  await submitGate(page, {
    name: 'Match Guest',
    email: s.recipientEmail,
  })
  await expectUnlockedCompare(page, s.projectTitle)
})

test('password_only requires the share password', async ({ page }) => {
  const s = share('password_only')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)

  await submitGate(page, { name: 'PW Guest', password: 'not-the-password' })
  await expectGateMessage(page, /password/i)

  await submitGate(page, { name: 'PW Guest', password: s.password! })
  await expectUnlockedCompare(page, s.projectTitle)
})

test('password_with_email_any_unverified needs password + any email', async ({ page }) => {
  const s = share('password_with_email_any_unverified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)

  await submitGate(page, {
    name: 'Combo Guest',
    password: s.password!,
    email: `${uid('combo')}@example.com`,
  })
  await expectUnlockedCompare(page, s.projectTitle)
})

test('password_with_email_matching needs password + matching email', async ({ page }) => {
  const s = share('password_with_email_matching')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)

  await submitGate(page, {
    name: 'Combo Match',
    password: s.password!,
    email: 'other@example.com',
  })
  await expectGateMessage(page, /match|email/i)

  await submitGate(page, {
    name: 'Combo Match',
    password: s.password!,
    email: s.recipientEmail,
  })
  await expectUnlockedCompare(page, s.projectTitle)
})

test('email_any_verified sends magic key then unlocks with key', async ({ page }) => {
  const s = share('email_any_verified')
  await openShareVote(page, s.magicToken)
  await withApi((api) =>
    completeVerifiedUnlock(page, api, s, {
      name: 'Verified Any',
      email: `${uid('vany')}@example.com`,
    }),
  )
})

test('email_matching_verified shows the email field', async ({ page }) => {
  const s = share('email_matching_verified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)
  await expectSendCodeView(page)
  await expectEmailFieldCount(page, 1)
  await expectGateMessage(page, /email address must be supplied/i)
})

test('password_with_email_matching_verified shows the email field', async ({ page }) => {
  const s = share('password_with_email_matching_verified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)
  await expectEmailFieldCount(page, 1)
})

test('recipient_email_verified hides email and notes the address on file', async ({ page }) => {
  const s = share('recipient_email_verified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)
  await expectSendCodeView(page)
  await expectEmailFieldCount(page, 0)
  await expectOnFileEmailHint(page)
  await expect(gateRoot(page).locator('.v-alert')).toHaveCount(0)
})

test('password_with_recipient_email_verified hides email and notes the address on file', async ({ page }) => {
  const s = share('password_with_recipient_email_verified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)
  await expectEmailFieldCount(page, 0)
  await expectOnFileEmailHint(page)
})

test('email_matching_verified requires matching email + magic key', async ({ page }) => {
  const s = share('email_matching_verified')
  await openShareVote(page, s.magicToken)
  await withApi((api) =>
    completeVerifiedUnlock(page, api, s, {
      name: 'Verified Match',
      email: s.recipientEmail,
    }),
  )
})

test('recipient_email_verified sends key to on-file email', async ({ page }) => {
  const s = share('recipient_email_verified')
  await openShareVote(page, s.magicToken)
  await withApi((api) =>
    completeVerifiedUnlock(page, api, s, {
      name: 'Recipient Verified',
      // optional typed email; empty is allowed server-side
    }),
  )
})

test('password_with_email_any_verified needs password + email + magic key', async ({ page }) => {
  const s = share('password_with_email_any_verified')
  await openShareVote(page, s.magicToken)
  await withApi((api) =>
    completeVerifiedUnlock(page, api, s, {
      name: 'PW Verified Any',
      email: `${uid('pvany')}@example.com`,
      password: s.password!,
    }),
  )
})

test('password_with_email_matching_verified needs password + match + magic key', async ({ page }) => {
  const s = share('password_with_email_matching_verified')
  await openShareVote(page, s.magicToken)
  await withApi((api) =>
    completeVerifiedUnlock(page, api, s, {
      name: 'PW Verified Match',
      email: s.recipientEmail,
      password: s.password!,
    }),
  )
})

test('password_with_recipient_email_verified needs password + magic key to on-file email', async ({ page }) => {
  const s = share('password_with_recipient_email_verified')
  await openShareVote(page, s.magicToken)
  await withApi((api) =>
    completeVerifiedUnlock(page, api, s, {
      name: 'PW Recipient Verified',
      password: s.password!,
    }),
  )
})

test('verified share URL shows Email Access Code, not a key field', async ({ page }) => {
  const s = share('email_any_verified')
  await openShareVote(page, s.magicToken)
  await expectGateVisible(page)
  await expectSendCodeView(page)
})

test('already have a code reveals the access code field', async ({ page }) => {
  const s = share('email_any_verified')
  await openShareVote(page, s.magicToken)
  await expectSendCodeView(page)
  await clickAlreadyHaveCode(page)
  await expectEnterCodeView(page)
})

test('query key opens enter-code with the value filled', async ({ page }) => {
  const s = share('email_any_verified')
  const preview = 'preview-key-from-query'
  await openShareVoteWithKey(page, s.magicToken, preview)
  await expectGateVisible(page)
  await expectEnterCodeView(page)
  await expect(page.getByLabel('Access code', { exact: true })).toHaveValue(preview)
})

test('path key rewrites to query and prefills enter-code', async ({ page }) => {
  const s = share('email_matching_verified')
  const preview = 'preview-key-from-path'
  await openShareVotePathKey(page, s.magicToken, preview)
  await expect(page).toHaveURL(new RegExp(`/share/vote/${encodeURIComponent(s.magicToken)}\\?key=`))
  await expectGateVisible(page)
  await expectEnterCodeView(page)
  await expect(page.getByLabel('Access code', { exact: true })).toHaveValue(preview)
})

test('email-with-code URL auto-unlocks when the key is valid', async ({ page }) => {
  const s = share('recipient_email_verified')
  await withApi(async (api) => {
    const send = await api.post(`/ext-ws/share/${encodeURIComponent(s.magicToken)}/vote`, {
      data: {
        display_name: 'Email Link',
        authorize_verification_email: true,
      },
    })
    expect(send.ok()).toBeTruthy()
    const sent = await send.json()
    expect(sent.sent_magic_access_message).toBeTruthy()

    await expect
      .poll(async () => {
        try {
          return await fetchLatestShareMagicKey(api, s.magicToken)
        } catch {
          return ''
        }
      }, { timeout: 20_000 })
      .not.toEqual('')

    const key = await fetchLatestShareMagicKey(api, s.magicToken)
    await openShareVoteWithKey(page, s.magicToken, key)
    await expectUnlockedCompare(page, s.projectTitle)
  })
})
