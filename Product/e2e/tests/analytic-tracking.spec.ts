import { expect, test } from '@playwright/test'

const trackingPayload = `
  <script>
    window.__analyticTrackingExecutions = (window.__analyticTrackingExecutions || 0) + 1;
    const replay = document.createElement('script');
    replay.dataset.testReplay = String(window.__analyticTrackingExecutions);
    document.head.appendChild(replay);
  </script>
`

test.beforeEach(async ({ page }) => {
  await page.route('**/api/_public/analytic-tracking', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      body: trackingPayload,
    })
  })
})

test('keeps a connected tracker stable when later head children are added', async ({ page }) => {
  await page.goto('/login')

  await expect.poll(() => page.evaluate(() => (
    (window as Window & { __analyticTrackingExecutions?: number }).__analyticTrackingExecutions
  ))).toBe(1)

  await page.evaluate(() => {
    const lateChild = document.createElement('meta')
    lateChild.name = 'late-head-mutation'
    document.head.appendChild(lateChild)
  })

  await expect.poll(() => page.locator('#analytic-tracking-script').count()).toBe(1)
  await expect.poll(() => page.locator('script[data-test-replay]').count()).toBe(1)
  await expect.poll(() => page.evaluate(() => (
    (window as Window & { __analyticTrackingExecutions?: number }).__analyticTrackingExecutions
  ))).toBe(1)
})

test('restores the tracker when it is genuinely removed', async ({ page }) => {
  await page.goto('/login')

  await expect.poll(() => page.evaluate(() => (
    (window as Window & { __analyticTrackingExecutions?: number }).__analyticTrackingExecutions
  ))).toBe(1)

  await page.locator('#analytic-tracking-script').evaluate(element => element.remove())

  await expect.poll(() => page.locator('#analytic-tracking-script').count()).toBe(1)
  await expect.poll(() => page.evaluate(() => (
    (window as Window & { __analyticTrackingExecutions?: number }).__analyticTrackingExecutions
  ))).toBe(2)
})
