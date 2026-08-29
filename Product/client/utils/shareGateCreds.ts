export const SHARE_GATE_AUTHORIZE_SEND_REASON =
  'Explicit authorization required to send a verification email'

export function mergeShareGateCreds(
  current: Record<string, unknown>,
  form: Record<string, unknown>,
  routeKey = '',
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...current, ...form }
  if (form.authorize_verification_email) {
    next.verification_magic_email_key = ''
    return next
  }
  if (!next.verification_magic_email_key && routeKey) {
    next.verification_magic_email_key = routeKey
  }
  return next
}

export function shareGateDenialAlert(
  failureReason: string | null | undefined,
  sentMagic = false,
): { message: string; type: 'error' | 'info' } {
  if (!failureReason || failureReason === SHARE_GATE_AUTHORIZE_SEND_REASON) {
    return { message: '', type: 'info' }
  }
  return { message: failureReason, type: sentMagic ? 'info' : 'error' }
}
