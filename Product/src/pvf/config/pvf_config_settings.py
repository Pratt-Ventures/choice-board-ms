from typing import Any, ClassVar, Union, Tuple, List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from os import environ, getpid, getcwd, path
from socket import gethostname

# TODO: There is an issue under uvicorn with process_name getting unset during initialize, globalsettings must be inadvertently recreated

# Some scripts run from project root, others run from /src, so we need to hint at the right place for the .env file
pvf_env_dir = path.abspath(getcwd())
if pvf_env_dir.endswith('/src'):
    pvf_env_dir = path.dirname(pvf_env_dir)

def get_env(type_var, env_var_name, default_value):
    """ retrieve environment value by env_var_name or its upper case, converted via typ_var, or default value
    """
    if env_var_name not in environ:
        env_var_name = env_var_name.upper()
    if env_var_name in environ:
        get_value = environ.get(env_var_name)
        if type_var is not None:
            get_value = type_var(get_value)
    else:
        get_value = default_value
    return get_value

def parse_sendgrid_template_ids(raw_value: str | None) -> dict[str, str]:
    """Parse template_code:sendgrid_id pairs. Format: code_1:d-abc,code_n:d-xyz"""
    if raw_value is None or not str(raw_value).strip():
        return {}
    template_ids: dict[str, str] = {}
    for pair in raw_value.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        code, sg_id = pair.split(":", 1)
        code = code.strip()
        sg_id = sg_id.strip()
        if code:
            template_ids[code] = sg_id
    return template_ids

def parse_csv_name_list(raw_value: str | list | None) -> list[str]:
    """Parse a comma-separated name list. Empty string or None becomes []. Already-a-list is stripped."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(token).strip() for token in raw_value if str(token).strip()]
    text = str(raw_value)
    if not text.strip():
        return []
    return [token.strip() for token in text.split(",") if token.strip()]

def get_trial_account_codes_dict(env_var_name, default_value):
    """ retrieve trial_code_list from default or environment value by env_var_name or its upper case, converted via typ_var, or default value
        format is: code_1:days,code_n:days
    """
    if env_var_name not in environ:
        env_var_name = env_var_name.upper()
    if env_var_name in environ:
        get_value = environ.get(env_var_name)
    else:
        get_value = default_value

    trial_code_list = [x.strip() for x in get_value.split(',') if x.strip() != '']
    trial_code_dict = {}
    for trial_code in trial_code_list:
        trial_code_parts = [x.strip().lower() for x in trial_code.split(':', 2)]
        code = trial_code_parts[0]
        days = int(trial_code_parts[1])
        trial_code_dict[code] = days
    # print('Loaded trial account codes: ', trial_code_dict)
    return trial_code_dict

class PvfGlobalSettings(BaseSettings):
    PVF_VERSION: str = "1.2.0"
    APPLICATION_NAME: str = environ.get("APPLICATION_NAME", "PV Framework App Name")

    model_config = SettingsConfigDict(env_file=path.join(pvf_env_dir, ".env"), extra="ignore")
    server_env: str = "local" # must be local, test or production ONLY
    computer_name: str = gethostname()
    environment_name: str = environ.get("ENVIRONMENT_NAME", "local-dev")
    process_name: str = "_not_specified_"
    process_id: int = getpid()

    PYTEST_ACTIVE: bool = bool(int(environ.get("PYTEST_ACTIVE", 0)))
    UNIQUE_CONFIGURATION_CHECK: bool = bool(int(environ.get("UNIQUE_CONFIGURATION_CHECK", 0)))  # only set to 1 in local .env, always 0 in example.env, so a check that env is custom

    APPLICATION_BASE_URL: str = environ.get("APPLICATION_BASE_URL", "http://localhost:9999")
    APPLICATION_SERVER_PORT: int = int(environ.get("APPLICATION_SERVER_PORT", 9999))
    APP_LOGIN_PATH: str = environ.get("APP_LOGIN_PATH", "login")
    APP_RESET_PASSWORD_URL: str = environ.get("APP_RESET_PASSWORD_URL", "forgot-password")

    # --- Startup-owned values (pvf_app_startup.yaml) -------------------------
    # Deployment-fixed feature switches and share vocabularies. These are set
    # ONLY by the pvf startup logic from pvf_app_startup.yaml (see
    # pvf.config.pvf_startup_config.apply_startup_config). They are declared
    # here as informational dummies; being ClassVars, pydantic-settings will
    # never populate them from .env or process environment, and __setattr__
    # below rejects any ordinary assignment.
    ACTIVATE_STRIPE_INTEGRATION: ClassVar[bool] = False
    ACTIVATE_BRANDING_IMAGE_STORE: ClassVar[bool] = False
    ACTIVATE_SHARE_LINKS: ClassVar[bool] = True
    ACTIVATE_EXTERNAL_API: ClassVar[bool] = True
    ACTIVATE_CUSTOMER_COMMUNICATION: ClassVar[bool] = True
    ACTIVATE_AI_AGENTS: ClassVar[bool] = False
    # Share link vocabularies (normalized to plain string lists at injection).
    # Defaults match the historical powerchoice values so import-time consumers
    # behave unchanged before startup injection runs.
    SHARE_OBJECT_ACTIONS: ClassVar[list[str]] = ["not_set", "vote", "vote_view", "report"]
    SHARE_ACCESS_OPERATIONS: ClassVar[list[str]] = ["not_set", "vote", "view", "report"]

    _STARTUP_VALUE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "ACTIVATE_STRIPE_INTEGRATION",
        "ACTIVATE_BRANDING_IMAGE_STORE",
        "ACTIVATE_SHARE_LINKS",
        "ACTIVATE_EXTERNAL_API",
        "ACTIVATE_CUSTOMER_COMMUNICATION",
        "ACTIVATE_AI_AGENTS",
        "SHARE_OBJECT_ACTIONS",
        "SHARE_ACCESS_OPERATIONS",
    })

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._STARTUP_VALUE_NAMES:
            raise RuntimeError(
                f"{name} is owned by pvf_app_startup.yaml and is read-only; "
                "only the pvf startup logic may set it"
            )
        super().__setattr__(name, value)

    def _inject_startup_values(self, values: dict[str, Any]) -> None:
        """Framework startup use only: apply values loaded from pvf_app_startup.yaml.

        Bypasses the read-only guard deliberately. Not part of the application-facing API.
        """
        for name, value in values.items():
            if name not in self._STARTUP_VALUE_NAMES:
                raise KeyError(f"{name} is not a startup-owned setting")
            object.__setattr__(self, name, value)

    BOOTSTRAP_SAMPLE_DATA: int = int(environ.get("BOOTSTRAP_SAMPLE_DATA", False))
    BOOTSTRAP_CUSTOMER_EMAIL: str = environ.get("BOOTSTRAP_CUSTOMER_EMAIL", None)
    BOOTSTRAP_ADMIN_USER_EMAIL: str = environ.get("BOOTSTRAP_ADMIN_USER_EMAIL", None)
    BOOTSTRAP_ADMIN_PASSWORD: str = environ.get("BOOTSTRAP_ADMIN_PASSWORD", None)
    BOOTSTRAP_NON_ADMIN_USER_EMAIL: str = environ.get("BOOTSTRAP_NON_ADMIN_USER_EMAIL", None)
    BOOTSTRAP_NON_ADMIN_PASSWORD: str = environ.get("BOOTSTRAP_NON_ADMIN_PASSWORD", None)

    APPLICATION_ACCOUNT_GRACE_PERIOD_DAYS: int = int(environ.get("APPLICATION_ACCOUNT_GRACE_PERIOD_DAYS", 3))   # provides this many days after expiration to keep service active
    APPLICATION_ACCOUNT_TRIAL_GRACE_PERIOD_DAYS: int = int(environ.get("APPLICATION_ACCOUNT_TRIAL_GRACE_PERIOD_DAYS", 3))   # provides this many days after expiration to keep service active

    PLATFORM_LINUX: int = int(environ.get("PLATFORM_LINUX", 1))
    DB_PATH_OR_CONNECTION_STRING: str = environ.get("DB_PATH_OR_CONNECTION_STRING", "sqlite:///local.db")    # Default to creating a local database
    DB_ECHO_SQL_TO_CONSOLE: bool = bool(int(environ.get("DB_ECHO_SQL_TO_CONSOLE", 0)))

    # Token secrets and settings
    JWT_SECRET_KEY:str = environ.get("JWT_SECRET_KEY", "enk1xmalq8pdnkb902x3hzo0uo9ayyoaubt2da57ucvh8pebelvfauyej2bzdak6jieso81ri")
    JWT_REFRESH_SECRET_KEY:str = environ.get("JWT_REFRESH", "12veui23ohkwanuignobggxbws9x5zxs4g8c29fxgb4d3gb7tl7vsz31p9uc3m0al82fitxbgedv")
    ACCESS_TOKEN_EXPIRE_MINUTES:int = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 10080))
    JWT_ALGORITHM: str = environ.get("JWT_ALGORITHM", "HS256")
    CLEARED_TOKEN_VALUE: str = environ.get("CLEARED_TOKEN_VALUE", "I'm no longer here, Where did I go?")
    PW_RESET_FLOODING_LIMIT_SECONDS: int = int(environ.get("PW_RESET_FLOODING_LIMIT_SECONDS", 90))
    PW_RESET_TOKEN_VALID_SECONDS: int = int(environ.get("PW_RESET_TOKEN_VALID_SECONDS", 7200))
    ACCOUNT_ACTIVATION_TOKEN_KEY: str = environ.get("ACCOUNT_ACTIVATION_TOKEN_KEY", "2b04wgwt4x4xvu2m6u3rfd")

    # Items with weird values (like TRIAL_ACCOUNT_CODES) need custom field validators to override the default
    # parser.  Otherwise Pydanting will try to parse this itself with a JSON validator and fail.
    # The default must be set to None to get the validator to run.

    # TRIAL_ACCOUNT_CODES: dict[str, Tuple[int, int]] = get_trial_account_codes_dict("TRIAL_ACCOUNT_CODES", "trial_account_30_days:30:100")  # sample, 30 day trial with 100 tokens granted with same expiration; set with =code:days:tokens,code:days:tokens,... becomes key = (days, tokens)
    CUSTOMER_ACTIVATION_URL: str = "activate-customer"
    TRIAL_ACCOUNT_CODES: dict[str, int] | None = None  # sample, days of trial for a given trial code. ; example trial_code_1:10,...,trial_code_N:30
    @field_validator("TRIAL_ACCOUNT_CODES", mode="before")
    def parse_trial_account_codes(cls, value):
        """Custom parser for TRIAL_ACCOUNT_CODES."""
        if isinstance(value, str):
            return get_trial_account_codes_dict("TRIAL_ACCOUNT_CODES", value)
        return get_trial_account_codes_dict("TRIAL_ACCOUNT_CODES", "trial_account_30_days:30:100")

    # Comma-separated field names stripped from user_record and customer_record on context/session
    # responses (multiple values allowed, e.g. stripe_settings,client_settings). Empty string or None
    # disables masking. Unset uses the default stripe_settings. Converted to list[str] once at load.
    CONTEXT_MASKED_FIELDS: list[str] | None = None
    @field_validator("CONTEXT_MASKED_FIELDS", mode="before")
    def parse_context_masked_fields(cls, value):
        """Custom parser for CONTEXT_MASKED_FIELDS."""
        if value is None:
            return ["stripe_settings"]
        return parse_csv_name_list(value)

    ACCESS_MAGIC_KEY_EXPIRATION_MINUTES: int = int(environ.get("ACCESS_MAGIC_KEY_EXPIRATION_MINUTES", 70))
    ACCESS_MAGIC_KEY_EXPIRATION_MESSAGE: str = environ.get("ACCESS_MAGIC_KEY_EXPIRATION_MESSAGE", "one hour")

    LOGIN_2FA_MODE: str = environ.get("LOGIN_2FA_MODE", "disabled") # disabled / sysadmins / admins / admins+optin / all
    LOGIN_2FA_VALIDITY_MINUTES: int = int(environ.get("LOGIN_2FA_VALIDITY_MINUTES", 15))
    LOGIN_2FA_VALIDITY_MESSAGE: str = environ.get("LOGIN_2FA_VALIDITY_MESSAGE", "15 minutes")
    LOGIN_2FA_RESEND_LIMIT_SECONDS: int = int(environ.get("LOGIN_2FA_RESEND_LIMIT_SECONDS", 90))
    token_security_digits_only: bool = bool(int(environ.get("TOKEN_SECURITY_DIGITS_ONLY", 0)))

    # Share link support (framework-generic; share type/action vocabularies are startup-owned above)
    VIEW_TOKEN_KEY: str = environ.get("VIEW_TOKEN_KEY", "view-token-key-change-in-env")
    ACCESS_VIEW_COOKIE: str = environ.get("ACCESS_VIEW_COOKIE", "pc_share_view")
    SHARE_LINK_REST_PW_HASH_KEY: str = environ.get("SHARE_LINK_REST_PW_HASH_KEY", "x6q9uuwmagcy717wioctg6")
    SHARE_LINK_EXPIRATION_DAYS: int = int(environ.get("SHARE_LINK_EXPIRATION_DAYS", 30))
    SHARE_LINK_COOKIE_EXPIRATION_DAYS: int = int(environ.get("SHARE_LINK_COOKIE_EXPIRATION_DAYS", 14))
    SHARE_LINK_EXPIRATION_MESSAGE: str = environ.get("SHARE_LINK_EXPIRATION_MESSAGE", "30 days")
    SHARE_GATE_THROTTLE_WINDOW_SECONDS: int = int(environ.get("SHARE_GATE_THROTTLE_WINDOW_SECONDS", 3600))
    SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR: int = int(environ.get("SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR", 60))
    SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR: int = int(environ.get("SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR", 20))
    SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR: int = int(environ.get("SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR", 10))

    SHARE_PROJECT_APP_VIEW_BASE_URL: str = "/share/"   # must match client share landing routes
    SHARE_PROJECT_APP_VIEW_SUFFIX_URL: str = ""   # optional suffix after magic token
    SHARE_WS_BASE_URL: str = "/ext-ws/share/"  # API path prefix used for share cookies
    # Security notes included in share invitation emails (plain text guidance for recipients)
    SHARE_SECURITY_PASSWORD_INCLUDED_NOTE: str = "A password is required to open this link. Password: {share_password}"
    SHARE_SECURITY_PASSWORD_SEPARATE_NOTE: str = "A password is required to open this link. The password was provided separately."
    SHARE_SECURITY_NOTE_OPEN_ACCESS: str = "This link is open access; no additional verification is required."
    SHARE_SECURITY_NOTE_EMAIL_ANY_UNVERIFIED: str = "You will be asked to enter an email address to continue."
    SHARE_SECURITY_NOTE_EMAIL_ANY_VERIFIED: str = "You will verify any email address via a one-time access key."
    SHARE_SECURITY_NOTE_EMAIL_MATCHING: str = "You must enter the email address this link was sent to."
    SHARE_SECURITY_NOTE_EMAIL_MATCHING_VERIFIED: str = "You must verify the email address this link was sent to via a one-time access key."
    SHARE_SECURITY_NOTE_RECIPIENT_EMAIL_VERIFIED: str = "A one-time access key will be sent to the email on file for this link."
    SHARE_SECURITY_NOTE_PASSWORD_ONLY: str = "A password is required to open this link."
    SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_ANY_UNVERIFIED: str = "A password and an email address are required to open this link."
    SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_ANY_VERIFIED: str = "A password is required, then any email is verified via a one-time access key."
    SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_MATCHING: str = "A password and the original recipient email are required."
    SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED: str = "A password is required, then the original recipient email is verified via a one-time access key."
    SHARE_SECURITY_NOTE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED: str = "A password is required, then a one-time access key is sent to the email on file."

    # UI option gating for share access modes. These flags limit the choices offered in the
    # client only; the backend gate supports every access mode regardless, so an application
    # can tailor options to its audience without disabling functionality.
    ENABLE_SHARE_OPEN_ACCESS : bool = bool(int(environ.get("ENABLE_SHARE_OPEN_ACCESS", 0)))                      # Access Url; Enter Name; Access granted.
    ENABLE_SHARE_EMAIL_ANY_UNVERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_EMAIL_ANY_UNVERIFIED", 1)))   # Access Url; Enter Name & Any Email (not verified); Access Granted.
    ENABLE_SHARE_EMAIL_ANY_VERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_EMAIL_ANY_VERIFIED", 1)))       # Access Url; Enter Name & Any Email; Token email sent; Follow link or enter key from token email; Access Granted.
    ENABLE_SHARE_EMAIL_MATCHING : bool = bool(int(environ.get("ENABLE_SHARE_EMAIL_MATCHING", 1)))               # Access Url; Enter Name & Email; Email must match share; Access Granted.
    ENABLE_SHARE_EMAIL_MATCHING_VERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_EMAIL_MATCHING_VERIFIED", 0)))   # Access Url; Enter Name & Email; Email must match share; Token email sent; Use link or key to verify; Access Granted.
    ENABLE_SHARE_RECIPIENT_EMAIL_VERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_RECIPIENT_EMAIL_VERIFIED", 1))) # Access Url; Enter Name Only; Token email sent (based on share value); Use link or key to verify; Access Granted.
    ENABLE_SHARE_PASSWORD_ONLY : bool = bool(int(environ.get("ENABLE_SHARE_PASSWORD_ONLY", 0)))                        # Access Url; Enter Name Only; Password required from share; Access Granted.
    ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_UNVERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_UNVERIFIED", 1)))   # Access Url; Enter Name & Any Email (not verified); Password required from share; Access Granted.
    ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_VERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_VERIFIED", 0)))       # Access Url; Enter Name & Any Email (verified); Password required from share; Token email sent; Use link or key to verify; Access Granted.
    ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING: bool = bool(int(environ.get("ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING", 0)))          # Access Url; Enter Name & Email; Email must match share; Password required from share; Access Granted.
    ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED", 0)))   # Access Url; Enter Name & Email; Email must match share; Password required from share; Token email sent; Use link or key to verify; Access Granted.
    ENABLE_SHARE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED : bool = bool(int(environ.get("ENABLE_SHARE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED", 0))) # Access Url; Enter Name Only; Password required from share; Token email sent (based on share value); Use link or key to verify; Access Granted.

    # External (customer toolkit) API signing
    CUSTOMER_API_INBOUND_HASH_KEY: str = environ.get("CUSTOMER_API_INBOUND_HASH_KEY", "265c0a4a9832bcd2c7ffd8eb89dc11ca")
    CUSTOMER_API_OUTBOUND_HASH_KEY: str = environ.get("CUSTOMER_API_OUTBOUND_HASH_KEY", "7aa7b7a445b96cdf2f5c701854b8af9c")
    CUSTOMER_API_TIME_TOLERANCE: int = int(environ.get("CUSTOMER_API_TIME_TOLERANCE", 4800))   # 80 minutes

    # Watcher process (callback delivery and other background modules)
    # Legacy: WATCHER_PROCESS_MODULE_LIST is deprecated — use src/pvf_app_watcher.yaml `types` instead.
    WATCHER_PROCESS_MODULE_LIST: list[str] = [x.strip() for x in environ.get("WATCHER_PROCESS_MODULE_LIST", "").split(',') if x.strip()]
    WATCHER_PROCESS_SHOW_API_CALLBACKS: bool = bool(int(environ.get("WATCHER_PROCESS_SHOW_API_CALLBACKS", 0)))  # if true, the watcher will display API callback summary as processed
    WATCHER_PROCESS_API_CALLBACKS: bool = bool(int(environ.get("WATCHER_PROCESS_API_CALLBACKS", 1)))  # if true, the watcher will process and deliver eligible API callbacks
    WATCHER_PROCESS_API_CALLBACKS_TAG: str = environ.get("WATCHER_PROCESS_API_CALLBACKS_TAG", "process_api_callbacks")  # tag for surrogate module types used in the watcher
    WATCHER_PROCESS_API_CALLBACKS_MAXIMUM_ATTEMPTS: int = int(environ.get("WATCHER_PROCESS_API_CALLBACKS_MAXIMUM_ATTEMPTS", 5))  # maximum number of attempts to deliver an API callback before it is considered failed
    WATCHER_PROCESS_API_CALLBACKS_RETRY_DELAYS: list[int] = [int(x.strip()) for x in environ.get("WATCHER_PROCESS_API_CALLBACKS_RETRY_DELAYS", "1,4,10,60,60,120,120,120,120,120").split(',')]
    WATCHER_SHORTER_BUSY_POLL_SLEEP: float = float(environ.get("WATCHER_SHORTER_BUSY_POLL_SLEEP", 1.0))  # seconds between polls while work is being found
    WATCHER_LONGER_IDLE_INCREASING_POLL_SLEEP: float = float(environ.get("WATCHER_LONGER_IDLE_INCREASING_POLL_SLEEP", 5.0))  # base seconds between polls once idle; grows by the exponential factor
    WATCHER_POLL_EXPONENTIAL_FACTOR: float = float(environ.get("WATCHER_POLL_EXPONENTIAL_FACTOR", 1.2))  # idle poll backoff multiplier
    WATCHER_POLL_MAXIMUM_SLEEP_TIME: float = float(environ.get("WATCHER_POLL_MAXIMUM_SLEEP_TIME", 30.0))  # cap on seconds between polls
    WATCHER_PROCESS_EMAIL_LISTENER_ENABLE: bool = bool(int(environ.get("WATCHER_PROCESS_EMAIL_LISTENER_ENABLE", 0)))  # reserved; no email listener processing is implemented
    WATCHER_PROCESS_EMAIL_LISTENER_TAG: str = environ.get("WATCHER_PROCESS_EMAIL_LISTENER_TAG", "process_email_listener")  # tag for surrogate module types used for email listener
    WATCHER_PROCESS_AI_AGENTS_TAG: str = environ.get("WATCHER_PROCESS_AI_AGENTS_TAG", "process_ai_agents")
    WATCHER_EMAIL_LISTENER_SUBMISSION_ADDRESS: str = environ.get("WATCHER_EMAIL_LISTENER_SUBMISSION_ADDRESS", "")
    # New watcher queue tunables (framework-owned, env-overridable; critical bindings remain in pvf_app_watcher.yaml)
    WATCHER_CAPTURE_PAYLOADS: bool = bool(int(environ.get("WATCHER_CAPTURE_PAYLOADS", "1")))
    WATCHER_NO_LOG_TYPES: list[str] = [x.strip() for x in environ.get("WATCHER_NO_LOG_TYPES", "").split(",") if x.strip()]

    MAX_REPORTS_PER_DAY: int = int(environ.get("MAX_REPORTS_PER_DAY", 8))

    # 
    USE_EMAIL_SERVICE: str | None = environ.get("USE_EMAIL_SERVICE", None) # None disables outbound email; SMTP-JINJA uses local templates and defined SMTP; SENDGRID uses sendgrid settings, account, and templates
    EMAIL_SYNC_ASYNC: str = environ.get("EMAIL_SYNC_ASYNC", "sync")  # sync, per-request, async
    EMAIL_LOCAL_ALLOW_DOMAINS: str = environ.get("EMAIL_LOCAL_ALLOW_DOMAINS", "mailinator.com")   # set to list of domains that are allowed in dev environment (note, an '*' entry allows any domain and disables this filtering, without setting the application as 'production')
    EMAIL_BRAND_NAME: str = environ.get("EMAIL_BRAND_NAME", "Power Choice Pro")

    EMAIL_SUPPORT_EMAIL: str = environ.get("EMAIL_SUPPORT_EMAIL", "")
    MAX_EMAILS_PER_DEST_PER_HOUR: int = int(environ.get("MAX_EMAILS_PER_DEST_PER_HOUR", 4))
    MAX_EMAILS_PER_DEST_PER_24_HOURS: int = int(environ.get("MAX_EMAILS_PER_DEST_PER_24_HOURS", 8))
    MAX_EMAILS_PER_REMOTE_IP_PER_HOUR_VERIFIED: int = int(environ.get("MAX_EMAILS_PER_REMOTE_IP_PER_HOUR_VERIFIED", 20))
    MAX_EMAILS_PER_REMOTE_IP_PER_HOUR: int = int(environ.get("MAX_EMAILS_PER_REMOTE_IP_PER_HOUR", 4))

    # Settings to use a direct SMTP sender.
    DIRECT_EMAIL_FROM_NAME: str = environ.get("DIRECT_EMAIL_FROM_NAME", 'Service')
    DIRECT_EMAIL_FROM_ADDRESS: str = environ.get("DIRECT_EMAIL_FROM_ADDRESS", 'no_reply@domain.com')
    DIRECT_EMAIL_SMTP_HOST: str = environ.get("DIRECT_EMAIL_SMTP_HOST", "smtp.example.com")
    DIRECT_EMAIL_SMTP_PORT: int = int(environ.get("DIRECT_EMAIL_SMTP_PORT", 587)) # often 465 for SSL
    DIRECT_EMAIL_SMTP_TLS: bool = bool(int(environ.get("DIRECT_EMAIL_SMTP_TLS", 1)))
    DIRECT_EMAIL_SMTP_SSL: bool = bool(int(environ.get("DIRECT_EMAIL_SMTP_SSL", 1)))
    DIRECT_EMAIL_SMTP_USER: str = environ.get("DIRECT_EMAIL_SMTP_USER", "")
    DIRECT_EMAIL_SMTP_PASSWORD: str = environ.get("DIRECT_EMAIL_SMTP_PASSWORD", "")
    DIRECT_EMAIL_SMTP_TIMEOUT: int = int(environ.get("DIRECT_EMAIL_SMTP_TIMEOUT", 20))
    DIRECT_TEMPLATE_DIRECTORY: str = environ.get("DIRECT_TEMPLATE_DIRECTORY", "../email_templates")

    # Used when the PVF llm interface logic is enabled
    AI_SERVICE: str = environ.get("AI_SERVICE", "opencode_go")  # opencode_go | opencode_zen | openrouter
    AI_API_KEY: str = environ.get("AI_API_KEY", "")
    AI_MODEL: str = environ.get("AI_MODEL", "glm-5.2")
    AI_BASE_URL: str = environ.get("AI_BASE_URL", "")
    AI_HTTP_TIMEOUT_SECONDS: float = float(environ.get("AI_HTTP_TIMEOUT_SECONDS", 30))
    AI_HTTP_RETRIES: int = int(environ.get("AI_HTTP_RETRIES", 3))
    PVF_FIELD_ENCRYPTION_KEY: str = environ.get("PVF_FIELD_ENCRYPTION_KEY", "")

    # Settings for SendGrid email service.
    SG_KEY: str = environ.get("SG_KEY", "Random-set-by-env!")
    SG_API_ENDPOINT: str = environ.get("SG_API_ENDPOINT", "https://api.sendgrid.com/v3/mail/send")
    SG_FROM_EMAIL: str = environ.get("SG_FROM_EMAIL", 'PowerChoice Service <no_reply@powerchoice.com>')
    SENDGRID_CONSOLE_JSON_REQUEST: bool = bool(environ.get("SENDGRID_CONSOLE_JSON_REQUEST", True))
    SENDGRID_CONSOLE_JSON_RESULT: bool = bool(environ.get("SENDGRID_CONSOLE_JSON_RESULT", True))
    SENDGRID_TEMPLATE_IDS: dict[str, str] | None = None  # template_code:sendgrid_id,... ; SMTP-only installs may leave empty

    @field_validator("SENDGRID_TEMPLATE_IDS", mode="before")
    def parse_sendgrid_template_ids_field(cls, value):
        """Custom parser for SENDGRID_TEMPLATE_IDS."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return parse_sendgrid_template_ids(value)
        return {}

    STRIPE_API_KEY_PRIMARY: str = environ.get("STRIPE_API_KEY_PRIMARY", "sk_test_insert-stripe-test-key-for-primary-customers")
    # STRIPE_ENDPOINT_SECRET_PRIMARY: str = environ.get("STRIPE_ENDPOINT_SECRET_PRIMARY", "whsec_hTomrupcMmGOax7v0qhbbXgr6PVhGEnM")
    STRIPE_ENDPOINT_SECRET_PRIMARY: str = environ.get("STRIPE_ENDPOINT_SECRET_PRIMARY", "whsec_specify in .env")
    STRIPE_HOOK_STR_PRIMARY: str = environ.get("STRIPE_HOOK_STR_PRIMARY", "specify in .env")
    # Product / Stripe Binding Information
    STRIPE_CALLBACK_PREFIX: str = environ.get("STRIPE_CALLBACK_PREFIX", "https://hooks.powerchoice.com/hook-stripe-events/")  # update in .env with correct domain/path
    STRIPE_CALLBACK_PREFIX_SANDBOX: str = environ.get("STRIPE_CALLBACK_PREFIX_SANDBOX", "https://hooks.powerchoice.com/hook-stripe-events-sandbox/")  # update in .env with correct domain/path
    
    def __init__(self):
        super().__init__()
        if self.server_env is None:
            self.server_env = environ.get("ENV", "local")
        self.server_env = self.server_env.lower()

    def is_local(self):
        return self.server_env == "local"
    
    def is_test(self):
        return self.server_env == "test"
    
    def is_prod(self):
        return self.server_env == "production"


pvf_settings = PvfGlobalSettings()