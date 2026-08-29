export const COMPARISON_QUESTION_MAX_LEN = 200
export const COMPARE_PROMPT_MAX_LEN = 280

export type CompareCriterion = {
  id?: number
  title?: string
  description?: string | null
  comparison_question?: string | null
  compare_prompt?: string | null
} | null | undefined

export type CompareOption = {
  id?: number
  title?: string | null
  description?: string | null
  compare_prompt?: string | null
} | null | undefined

export function trimmedComparisonQuestion(raw: string | null | undefined): string | null {
  const t = String(raw || '').trim()
  if (!t) return null
  return t.length > COMPARISON_QUESTION_MAX_LEN ? t.slice(0, COMPARISON_QUESTION_MAX_LEN) : t
}

export function trimmedComparePrompt(raw: string | null | undefined): string | null {
  const t = String(raw || '').trim()
  if (!t) return null
  return t.length > COMPARE_PROMPT_MAX_LEN ? t.slice(0, COMPARE_PROMPT_MAX_LEN) : t
}

export function hasCustomComparisonQuestion(criterion: CompareCriterion): boolean {
  return trimmedComparePrompt((criterion as any)?.compare_prompt) != null
}

export function hasComparePrompt(criterion: CompareCriterion): boolean {
  return trimmedComparePrompt((criterion as any)?.compare_prompt) != null
}

export function optionCompareQuestion(criterion: CompareCriterion): string {
  const cp = trimmedComparePrompt((criterion as any)?.compare_prompt)
  if (cp) return cp
  return 'Which option is better?'
}

export function optionCompareTitle(criterion: CompareCriterion, criterionId?: number | null): string {
  const title = String(criterion?.title || '').trim()
  if (title) return title
  if (criterionId == null) return 'Overall'
  return ''
}

export function factorDetailsCopy(criterion: CompareCriterion, criterionId?: number | null): { title: string, description: string } {
  const title = optionCompareTitle(criterion, criterionId) || 'Factor'
  const description = String(criterion?.description || '').trim()
  return { title, description }
}

export function optionDisplayTitle(option: CompareOption): string {
  const cp = trimmedComparePrompt((option as any)?.compare_prompt)
  if (cp) return cp
  return String(option?.title || '').trim()
}

export function optionDisplayDescription(option: CompareOption): string {
  return String(option?.description || '').trim()
}
