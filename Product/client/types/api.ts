export interface WsResultPackage {
  failure_reason?: string
  log_id?: number
}

export interface TeamMember {
  id: number
  name: string
  email: string
  customer_admin: boolean
  created_date: string
}

export interface UserRecord {
  id: number
  name: string
  email: string
  phone?: string | null
  customer_id: number
  customer_admin: boolean
  power_user_mode?: number
  system_user_mode?: number
  access_disabled?: number
  use_2fa?: boolean
  create_date?: string
  modify_date?: string
  deleted_date?: string | null
  client_settings?: Record<string, unknown> | null
}

export interface UserResultMany extends WsResultPackage {
  user_info_list?: UserRecord[]
}

export interface UserResultOne extends WsResultPackage {
  user_info?: UserRecord | null
}

export interface UserResultOneId extends WsResultPackage {
  user_id?: number | null
}

export interface CustomerRecord {
  id: number
  customer_email: string
  customer_account?: string | null
  customer_name: string
  customer_phone?: string | null
  account_status?: string
  customer_activated?: boolean
  use_2fa?: boolean
  trial_activation_date?: string | null
  trial_expiration_date?: string | null
  service_expiration_date?: string | null
  create_date?: string
  modify_date?: string
}

export interface UserCustomerContextView extends WsResultPackage {
  context_timestamp: string
  user_id: number
  name: string
  email: string
  is_customer_admin: boolean
  customer_id: number
  customer_name?: string | null
  customer_email?: string | null
  stripe_customer_id?: string | null
  trial_expiration_days?: number | null
  stripe_callback_prefix?: string | null
  stripe_callback_prefix_sandbox?: string | null
  user_record?: UserRecord | null
  customer_record?: CustomerRecord | null
  team_info?: TeamMember[] | null
  settings?: Record<string, unknown> | null
  server_version?: string | null
  client_version?: string | null
}

export interface LoginResponse extends WsResultPackage {
  access_token?: string
  message?: string
  two_factor_required?: boolean
  validity_minutes?: number
  user_id?: number
  user_name?: string
}

export interface Login2FAChallenge extends WsResultPackage {
  two_factor_required: boolean
  message?: string
  validity_minutes?: number
}

export interface SetUse2FAResult extends WsResultPackage {
  prior?: boolean | null
  new?: boolean | null
  use_2fa?: boolean | null
}

export interface CustomerUserCreateResult extends WsResultPackage {
  user_id?: number | null
  customer_id?: number | null
  message?: string
}

export interface SnackbarState {
  show: boolean
  message: string
  color: string
}

// ---- Projects ----

export interface CustomerProject {
  id: number
  customer_id: number
  magic_token?: string | null
  project_tag: string
  project_title?: string | null
  project_description?: string | null
  project_exclusive_mode?: boolean
  ranking_mode?: string
  private_participation?: boolean
  /** comparisons | balanced | participants_normalized */
  participant_influence_mode?: string
  participant_influence_min_comparisons?: number
  /** Factor weight floor scale alpha×(n−1); 0.1–0.9, default 0.5 */
  factor_weight_floor_alpha?: number
  min_expected_passes?: number
  max_recommended_passes?: number
  include_ai_agents?: boolean
  ai_voter_models?: string[]
  option_questions_per_group?: number
  factor_questions_per_group?: number
  option_questions_per_group_explicit?: boolean
  factor_questions_per_group_explicit?: boolean
  project_created_by?: number
  project_criteria_template?: number
  disabled?: boolean
  end_time?: string | null
  create_date?: string
  modify_date?: string
  deleted_date?: string | null
}

export interface CustomerProjectResultOne extends WsResultPackage {
  customer_project_info?: CustomerProject | null
  /** True when private participation is on and non-creator comparisons exist */
  private_participation_locked?: boolean
}

export interface CustomerProjectResultMany extends WsResultPackage {
  customer_project_info_list?: CustomerProject[] | null
}

export interface ProjectListMetrics {
  stability?: number
  confidence?: number
  completion?: number
  coverage?: number
  accuracy?: number
}

export interface ProjectListSummaryItem {
  project: CustomerProject
  alternative_count: number
  factor_count: number
  observation_count: number
  participant_count: number
  metrics: ProjectListMetrics
}

export interface ProjectListSummaryResult extends WsResultPackage {
  projects?: ProjectListSummaryItem[]
}

export interface ProjectPageContentItem {
  id: number
  title?: string | null
  description?: string | null
  disabled?: boolean
}

export interface AiAgentCounts {
  requested: number
  in_flight: number
  completed: number
}

export interface HumanParticipantActiveItem {
  label: string
  comparison_count: number
  participant_id?: number | null
}

export interface HumanParticipantPendingItem {
  label: string
  days_pending: number
  email?: string | null
  participant_id?: number | null
  share_id?: number | null
}

export interface AnonymousShareItem {
  label: string
  activated: number
  share_id?: number | null
}

export interface HumanParticipantsSummary {
  active?: HumanParticipantActiveItem[]
  pending?: HumanParticipantPendingItem[]
  anonymous_shares?: AnonymousShareItem[]
}

export interface AiParticipantStatusItem {
  model_key: string
  display_name: string
  status: string
  pairs_answered: number
  pairs_remaining: number
}

export interface ProjectPageSummaryResult extends WsResultPackage {
  project?: CustomerProject | null
  alternatives?: ProjectPageContentItem[]
  factors?: ProjectPageContentItem[]
  my_observation_count?: number
  participant_count?: number
  target_comparisons_est?: number
  max_comparisons_est?: number
  active_participant_count?: number
  ai_agent_counts?: AiAgentCounts
  human_participants?: HumanParticipantsSummary
  ai_participants?: AiParticipantStatusItem[]
  my_metrics?: ProjectListMetrics
}

export interface CustomerProjectDeleteResult extends WsResultPackage {
  success?: boolean
  customer_project_id?: number | null
  customer_project_tag?: string | null
}

export interface CustomerProjectAlternative {
  id: number
  customer_id: number
  project_id: number
  alternative_title?: string | null
  alternative_description?: string | null
  compare_prompt?: string | null
  disabled?: boolean
  create_date?: string
  modify_date?: string
  deleted_date?: string | null
}

export interface CustomerProjectAlternativeResultOne extends WsResultPackage {
  alternative_info?: CustomerProjectAlternative | null
}

export interface CustomerProjectAlternativeResultMany extends WsResultPackage {
  alternative_info_list?: CustomerProjectAlternative[] | null
}

export interface CustomerProjectFactor {
  id: number
  customer_id: number
  project_id: number
  factor_title?: string | null
  factor_description?: string | null
  comparison_question?: string | null
  compare_prompt?: string | null
  factor_polarity_positive?: boolean
  factor_polarity_note?: string | null
  disabled?: boolean
  create_date?: string
  modify_date?: string
  deleted_date?: string | null
}

export interface CustomerProjectFactorResultOne extends WsResultPackage {
  factor_info?: CustomerProjectFactor | null
}

export interface CustomerProjectFactorResultMany extends WsResultPackage {
  factor_info_list?: CustomerProjectFactor[] | null
}

export interface FactorTemplateEntry {
  factor_title: string
  factor_description?: string | null
  comparison_question?: string | null
  factor_polarity_positive?: boolean
  factor_polarity_note?: string | null
}

export interface OptionTemplateEntry {
  alternative_title?: string | null
  alternative_description?: string | null
}

export interface FactorTemplate {
  id: number
  customer_id: number
  enable_global_share?: boolean
  factor_template_title?: string | null
  factor_template_description?: string | null
  factor_template_entries?: FactorTemplateEntry[] | null
  option_template_entries?: OptionTemplateEntry[] | null
  use_with_projects?: boolean
  use_with_options?: boolean
  use_with_factors?: boolean
  project_exclusive_mode?: boolean
  private_participation?: boolean
  disabled?: boolean
  create_date?: string
  modify_date?: string
  deleted_date?: string | null
}

/** @deprecated Prefer FactorTemplate — same shape, broader scope */
export type ProjectTemplate = FactorTemplate

export interface FactorTemplateResultOne extends WsResultPackage {
  factor_template_info?: FactorTemplate | null
}

export interface FactorTemplateResultMany extends WsResultPackage {
  factor_template_info_list?: FactorTemplate[] | null
}

// ---- Votes ----

export interface VoteParticipant {
  id: number
  customer_id: number
  project_id: number
  user_id?: number | null
  share_id?: number | null
  participant_key: string
  display_name?: string | null
  email?: string | null
  source?: string
  observation_count?: number
  is_complete?: boolean
  last_activity_date?: string | null
  create_date?: string
}

export interface VoteObservation {
  id: number
  customer_id: number
  project_id: number
  participant_id: number
  observation_type: 'alternative' | 'criteria'
  criterion_id?: number | null
  item_ids: number[]
  response: 'winner' | 'tie' | 'unsure' | 'skipped'
  winner_id?: number | null
  predicted_id?: number | null
  predicted_probability?: number | null
  prediction_correct?: boolean | null
  client_event_id?: string | null
  algorithm_version?: string
  create_date?: string
}

export interface ParticipantBundleResult extends WsResultPackage {
  participant_info?: VoteParticipant | null
  observations?: VoteObservation[]
  next_questions?: unknown[]
  ranking_settings?: Record<string, unknown>
}

export interface ProjectReportResult extends WsResultPackage {
  project_id?: number | null
  report?: Record<string, unknown>
}

export interface ProjectVoteBundleResult extends WsResultPackage {
  project_id?: number | null
  participants?: VoteParticipant[]
  observations?: VoteObservation[]
  report?: Record<string, unknown>
}

// ---- Sharing ----

export interface ShareLink {
  id: number
  magic_token?: string | null
  customer_id?: number | null
  user_id?: number | null
  shared_type: string
  shared_entity_db_id: number
  link_auto_send?: boolean
  shared_with_company_name?: string | null
  shared_with_person_name?: string | null
  shared_with_email?: string | null
  share_link_name?: string | null
  share_link_expiration?: number
  access_mode: string
  /** Never returned as plaintext after create; activity API clears this and sets password_set. */
  share_password?: string | null
  share_password_in_email?: boolean
  cookie_duration?: number
  share_link_enabled?: boolean
  create_date?: string
  modify_date?: string
}

export interface CreateShareLinkResponse extends WsResultPackage {
  link_info?: ShareLink | null
  link_url?: string | null
  link_email_sent?: boolean | null
}

export interface SendShareInvitationResponse extends WsResultPackage {
  link_email_sent?: boolean | null
  was_resend?: boolean
  email_type?: string | null
}

export interface ShareLinkAccess {
  id: number
  share_id?: number
  captured_email?: string | null
  captured_display_name?: string | null
  access_count?: number
  create_date?: string
  modify_date?: string
}

export interface ShareLinkMagicKey {
  id: number
  share_id?: number
  captured_email?: string | null
  captured_display_name?: string | null
  accessed_date?: string | null
  create_date?: string
}

export interface ShareLinkAuthsAccesses {
  project_id: number
  share_id: number
  share_link?: ShareLink | null
  share_link_magic_keys?: ShareLinkMagicKey[]
  share_link_accesses?: ShareLinkAccess[]
  share_link_url?: string | null
  password_set?: boolean
  session_count?: number
  total_hits?: number
  magic_keys_issued?: number
  magic_keys_used?: number
  participant_count?: number
  observation_count?: number
  invite_email_sent?: boolean
  invite_email_last_sent?: string | null
  share_link_expired?: boolean
}

export interface ShareActivityResultsSingle extends WsResultPackage {
  share_info_list?: ShareLinkAuthsAccesses[]
  unknown_keys?: ShareLinkMagicKey[]
  unknown_accesses?: ShareLinkAccess[]
}

export interface ShareActivityResultsMulti extends WsResultPackage {
  share_info_list_per_project_id?: Record<string, ShareLinkAuthsAccesses[]>
  unknown_keys?: ShareLinkMagicKey[]
  unknown_accesses?: ShareLinkAccess[]
}

export interface BrandingImageResult extends WsResultPackage {
  has_image?: boolean
  content_type?: string | null
  file_name?: string | null
  original_file_name?: string | null
  original_byte_size?: number | null
  byte_size?: number | null
  was_compressed?: boolean
  modify_date?: string | null
}

export interface BrandingMeta {
  customer_name?: string | null
  has_customer_image?: boolean
  customer_image_modify_date?: string | null
  project_title?: string | null
  has_project_image?: boolean
  project_image_modify_date?: string | null
}

export interface ShareBrandingMetaResult extends WsResultPackage {
  branding?: BrandingMeta | null
}

export interface ShareAccessPayload extends WsResultPackage {
  share_result_status?: Record<string, unknown> | null
  project?: {
    project_id: number
    project_tag?: string | null
    project_title?: string | null
    project_description?: string | null
    project_exclusive_mode?: boolean
    ranking_mode?: string
    private_participation?: boolean
    alternative_count?: number
    factor_count?: number
    disabled?: boolean
    end_time?: string | null
    collection_ending_soon?: boolean
    collection_closed?: boolean
    customer_name?: string | null
    has_customer_branding_image?: boolean
    has_project_branding_image?: boolean
  } | null
  alternatives?: CustomerProjectAlternative[]
  factors?: CustomerProjectFactor[]
  personal_vote?: {
    participant?: VoteParticipant
    observations?: VoteObservation[]
    observation_count?: number
    is_complete?: boolean
  } | null
  participant_id?: number | null
  completion_status?: Record<string, unknown>
  report?: Record<string, unknown>
  observation_info?: VoteObservation | null
  next_questions?: unknown[]
  ranking_settings?: Record<string, unknown>
  viewer?: {
    display_name?: string | null
    organization?: string | null
    email?: string | null
  } | null
  access_mode?: string
  verification_password_needed?: boolean
  verification_email_needed?: boolean
  verification_original_email_needed?: boolean
  verification_email_send_link_mode?: boolean
  verification_email_magic_link_needed?: boolean
  verification_password_not_supplied?: boolean
  verification_password_incorrect?: boolean
  verification_email_not_supplied?: boolean
  verification_magic_link_incorrect?: boolean
  verification_magic_link_expired?: boolean
  verification_magic_link_used?: boolean
  sent_magic_access_message?: boolean
}

export type UserCommunicationKind = 'bug_report' | 'suggestion'
export type BugImpact = 'minor' | 'moderate' | 'blocking'
export type SuggestionImportance = 'nice_to_have' | 'important' | 'very_important'
export type ProductArea =
  | 'projects'
  | 'sharing'
  | 'compare'
  | 'results'
  | 'templates'
  | 'team'
  | 'account'
  | 'other'

export interface UserCommunicationRow {
  id: number
  kind: UserCommunicationKind | string
  customer_id: number
  user_id: number
  customer_name?: string | null
  user_name?: string | null
  has_attachment?: boolean
  attachment_filename?: string | null
  attachment_content_type?: string | null
  summary?: string | null
  what_happened?: string | null
  expected_happened?: string | null
  steps_to_reproduce?: string | null
  impact?: BugImpact | string | null
  suggestion?: string | null
  accomplish_goal?: string | null
  product_area?: ProductArea | string | null
  importance?: SuggestionImportance | string | null
  acknowledge_date?: string | null
  acknowledge_user_id?: number | null
  acknowledge_note?: string | null
  response_date?: string | null
  response_user_id?: number | null
  response_note?: string | null
  resolution_date?: string | null
  resolution_user_id?: number | null
  resolution_note?: string | null
  create_date?: string | null
  modify_date?: string | null
}

export interface UserCommunicationSubmitResult extends WsResultPackage {
  stored?: boolean
  limit_warning?: boolean
  submitted_in_window?: number
  max_per_day?: number
  submission_id?: number | null
}

export interface UserCommunicationResultOne extends WsResultPackage {
  item?: UserCommunicationRow | null
}

export interface UserCommunicationResultMany extends WsResultPackage {
  items?: UserCommunicationRow[] | null
  total_count?: number
}

export interface UserCommunicationDeleteResult extends WsResultPackage {
  success?: boolean
  submission_id?: number | null
}

export interface UserCommunicationAdminModifyPayload {
  id: number
  acknowledge_date_action?: 'set' | 'clear' | null
  response_date_action?: 'set' | 'clear' | null
  resolution_date_action?: 'set' | 'clear' | null
  acknowledge_note?: string | null
  response_note?: string | null
  resolution_note?: string | null
}
