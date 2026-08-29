from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from os import environ, getpid
from socket import gethostname

from .config_settings import settings
from ..pvf.bindings.pvf_invocation import PvfClientAuthSettings

class ClientSettings(PvfClientAuthSettings, BaseSettings):
    process_name: str = Field(default=settings.process_name, description="the computer from which the service response was generated")
    environment_name: str = Field(default=settings.environment_name, description="the attributed environment name from which the service response was generated")
    computer_name: str = Field(default=settings.computer_name, description="the computer from which the service response was generated")
    process_id: int = Field(default=settings.process_id, description="the computer process id from which the service response was generated")
    server_env: str = Field(default=settings.server_env, description="Server environment settings for the computer generating the response.")
    coherence_method: str = Field(
        default="spearman",
        description="Rank agreement algorithm for multi-participant reports: spearman | kendall.",
    )
    # each of these enables the respective PvfShareAccessCheckMode value in the user interface for share links.
    # all are implemented in the backend and front end flows, but options may be reduced for simplicity here.
    enable_share_open_access : bool = settings.ENABLE_SHARE_OPEN_ACCESS   # Access Url; Enter Name; Access granted.
    enable_share_email_any_unverified : bool = settings.ENABLE_SHARE_EMAIL_ANY_UNVERIFIED   # Access Url; Enter Name & Any Email (not verified); Access Granted.
    enable_share_email_any_verified : bool = settings.ENABLE_SHARE_EMAIL_ANY_VERIFIED       # Access Url; Enter Name & Any Email; Token email sent; Follow link or enter key from token email; Access Granted.
    enable_share_email_matching : bool = settings.ENABLE_SHARE_EMAIL_MATCHING               # Access Url; Enter Name & Email; Email must match share; Access Granted.
    enable_share_email_matching_verified : bool = settings.ENABLE_SHARE_EMAIL_MATCHING_VERIFIED   # Access Url; Enter Name & Email; Email must match share; Token email sent; Use link or key to verify; Access Granted.
    enable_share_recipient_email_verified : bool = settings.ENABLE_SHARE_RECIPIENT_EMAIL_VERIFIED # Access Url; Enter Name Only; Token email sent (based on share value); Use link or key to verify; Access Granted.
    enable_share_password_only : bool = settings.ENABLE_SHARE_PASSWORD_ONLY                        # Access Url; Enter Name Only; Password required from share; Access Granted.
    enable_share_password_with_email_any_unverified : bool = settings.ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_UNVERIFIED   # Access Url; Enter Name & Any Email (not verified); Password required from share; Access Granted.
    enable_share_password_with_email_any_verified : bool = settings.ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_VERIFIED       # Access Url; Enter Name & Any Email (verified); Password required from share; Token email sent; Use link or key to verify; Access Granted.
    enable_share_password_with_email_matching : bool = settings.ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING          # Access Url; Enter Name & Email; Email must match share; Password required from share; Access Granted.
    enable_share_password_with_email_matching_verified : bool = settings.ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED   # Access Url; Enter Name & Email; Email must match share; Password required from share; Token email sent; Use link or key to verify; Access Granted.
    enable_share_password_with_recipient_email_verified : bool = settings.ENABLE_SHARE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED # Access Url; Enter Name Only; Password required from share; Token email sent (based on share value); Use link or key to verify; Access Granted.
    ANALYTIC_TRACKING_TOKEN: str = settings.ANALYTIC_TRACKING_TOKEN
    ANALYTIC_TRACKING_STATIC_SCRIPT: str = settings.ANALYTIC_TRACKING_STATIC_SCRIPT


    @field_validator("coherence_method")
    @classmethod
    def _clamp_coherence(cls, v: str) -> str:
        m = (v or "spearman").strip().lower()
        return m if m in ("spearman", "kendall") else "spearman"

client_settings = ClientSettings()
