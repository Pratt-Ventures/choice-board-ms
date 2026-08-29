export function quotaCopy(submittedInWindow?: number, maxPerDay?: number): string {
  if (!submittedInWindow || !maxPerDay) return ''
  if (submittedInWindow <= maxPerDay / 3) return ''
  return `We limit submissions in a 24 hour period due to our capacity. You have submitted ${submittedInWindow} of ${maxPerDay} as of now.`
}
