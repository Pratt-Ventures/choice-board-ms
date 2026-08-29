import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test'
import { fetchLatestShareMagicKey, type SeededShare } from './api'

/** Vuetify outlined fields expose the label via associated control text. */
export async function fillLabeled(page: Page, label: string, value: string) {
  const field = page.getByLabel(label, { exact: true })
  await expect(field).toBeVisible()
  await field.fill(value)
}

export async function clickContinue(page: Page) {
  await page.getByRole('button', { name: 'Continue' }).click()
}

export async function clickSendCode(page: Page) {
  await page.getByRole('button', { name: 'Email Access Code' }).click()
}

export async function clickAlreadyHaveCode(page: Page) {
  await page.getByRole('button', { name: 'already have a code' }).click()
}

export async function openShareVote(page: Page, magicToken: string) {
  await page.goto(`/share/vote/${encodeURIComponent(magicToken)}`)
}

export async function openShareVoteWithKey(page: Page, magicToken: string, key: string) {
  await page.goto(`/share/vote/${encodeURIComponent(magicToken)}?key=${encodeURIComponent(key)}`)
}

export async function openShareVotePathKey(page: Page, magicToken: string, key: string) {
  await page.goto(`/share/vote/${encodeURIComponent(magicToken)}/${encodeURIComponent(key)}`)
}

export function gateRoot(page: Page): Locator {
  return page.locator('.share-gate')
}

export async function expectGateVisible(page: Page) {
  await expect(gateRoot(page)).toBeVisible()
  await expect(page.getByText('Secure access')).toBeVisible()
}

export async function expectSendCodeView(page: Page) {
  await expect(page.getByRole('button', { name: 'Email Access Code' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'already have a code' })).toBeVisible()
  await expect(page.getByLabel('Access code', { exact: true })).toHaveCount(0)
}

export async function expectEmailFieldCount(page: Page, count: number) {
  await expect(page.getByLabel('Email', { exact: true })).toHaveCount(count)
}

export async function expectOnFileEmailHint(page: Page) {
  await expect(page.getByText('We will send a one-time access code to the email on file.')).toBeVisible()
}

export async function expectEnterCodeView(page: Page) {
  await expect(page.getByLabel('Access code', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Continue' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'send/resend code to email' })).toBeVisible()
}

export async function expectUnlockedCompare(page: Page, projectTitle?: string) {
  await expect(gateRoot(page)).toHaveCount(0, { timeout: 25_000 })
  await expect(page.locator('main .eyebrow', { hasText: 'Comparing' })).toBeVisible({ timeout: 25_000 })
  if (projectTitle) {
    await expect(page.locator('main .page-title', { hasText: projectTitle })).toBeVisible()
  }
}

export async function expectGateMessage(page: Page, re: RegExp) {
  await expect(gateRoot(page).locator('.v-alert').filter({ hasText: re })).toBeVisible()
}

export type GateSubmitOptions = {
  name?: string
  email?: string
  password?: string
  magicKey?: string
  magicKeyLabel?: string
  authorizeSend?: boolean
}

export async function submitGate(page: Page, opts: GateSubmitOptions) {
  if (opts.name != null) await fillLabeled(page, 'Your name', opts.name)
  if (opts.email != null) await fillLabeled(page, 'Email', opts.email)
  if (opts.password != null) await fillLabeled(page, 'Password', opts.password)
  if (opts.magicKey != null) await fillLabeled(page, opts.magicKeyLabel ?? 'Access code', opts.magicKey)
  if (opts.authorizeSend) {
    await clickSendCode(page)
    return
  }
  await clickContinue(page)
}

/** Verified modes: request key, pull it from test-helper, redeem. */
export async function completeVerifiedUnlock(
  page: Page,
  api: APIRequestContext,
  share: SeededShare,
  opts: {
    name: string
    email?: string
    password?: string
  },
) {
  await expectGateVisible(page)
  await expectSendCodeView(page)
  await submitGate(page, {
    name: opts.name,
    email: opts.email,
    password: opts.password,
    authorizeSend: true,
  })

  await expect
    .poll(async () => {
      try {
        return await fetchLatestShareMagicKey(api, share.magicToken)
      } catch {
        return ''
      }
    }, { timeout: 20_000 })
    .not.toEqual('')

  const key = await fetchLatestShareMagicKey(api, share.magicToken)
  await expectEnterCodeView(page)
  await submitGate(page, {
    name: opts.name,
    email: opts.email,
    password: opts.password,
    magicKey: key,
  })
  await expectUnlockedCompare(page, share.projectTitle)
}
