"""Analytic tracking payload resolver.

Derives the effective script string from GlobalSettings / ClientSettings
with guard conditions and whitelist suffix matching.

Rules (strict, per plan Q2/Q3):
- Both ANALYTIC_TRACKING_TOKEN and ANALYTIC_TRACKING_STATIC_SCRIPT must be non-empty/whitespace, otherwise no injection.
- Empty whitelist means none enabled (suppress).
- Single entry '*' means allow all domains.
- Otherwise every absolute URL (src/href) in the effective string must have a host suffix match against the whitelist (case-insensitive, dot-boundary for domain suffix, port-aware when entry contains ':').
- Token substitution replaces all occurrences of "{ANALYTIC_TRACKING_TOKEN}".
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_PLACEHOLDER = "{ANALYTIC_TRACKING_TOKEN}"
_SRC_HREF_RE = re.compile(r'\b(?:src|href)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _normalize_whitelist(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        # CSV string
        return [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(s).strip() for s in raw if str(s).strip()]
    return []


def _extract_urls(script: str) -> list[str]:
    return _SRC_HREF_RE.findall(script or "")


def _is_whitelisted_url(url: str, whitelist: list[str]) -> bool:
    """Suffix match per spec.

    - Relative URLs (no host/netloc) are allowed (same-origin).
    - Entry with ':' is matched against netloc (host:port), otherwise against hostname.
    - Matching is case-insensitive, suffix with dot-boundary to avoid "notrybbit.io" matching "rybbit.io".
    - '*' already handled at caller.
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        netloc = (parsed.netloc or "").lower()
        # Relative URL: no host, no netloc -> allow
        if not hostname and not netloc:
            # urlparse may still have path only; treat as relative -> allow
            if not parsed.scheme:
                return True
            return True
        for entry in whitelist:
            e = entry.strip().lower()
            if e == "*":
                return True
            if not e:
                continue
            if ":" in e:
                cand = netloc
                # Exact or suffix with dot
                if cand == e or cand.endswith("." + e) or cand.endswith(e):
                    # For port-bearing entries, require dot-boundary or exact. Use strict dot for domain part.
                    # Allow cand == e or cand.endswith("." + e)
                    if cand == e or cand.endswith("." + e):
                        return True
                    # Fallback: raw suffix (handles edge where entry includes dot+port)
                    if cand.endswith(e):
                        # ensure preceding char is '.' or ':' to avoid partial match
                        idx = cand.rfind(e)
                        if idx > 0 and cand[idx - 1] in (".", ":"):
                            return True
                        if idx == 0:
                            return True
            else:
                # match against hostname
                if not hostname:
                    continue
                if hostname == e or hostname.endswith("." + e):
                    return True
        return False
    except Exception:
        return False


def get_effective_tracking_script() -> str | None:
    """Return effective payload string or None when injection should be suppressed.

    Reads from GlobalSettings (src.config.config_settings.settings) which is the
    source of truth after merge_pvf_settings_into; client_config mirrors it but
    resolver uses settings directly for unauthenticated endpoint (no client context).
    """
    from ..config.config_settings import settings

    token = (getattr(settings, "ANALYTIC_TRACKING_TOKEN", "") or "").strip()
    script = (getattr(settings, "ANALYTIC_TRACKING_STATIC_SCRIPT", "") or "").strip()
    whitelist_raw = getattr(settings, "ANALYTIC_TRACKING_WHITELIST", [])

    whitelist = _normalize_whitelist(whitelist_raw)

    # Guard: requires both populated (strict)
    if not token:
        return None
    if not script:
        return None

    # Empty whitelist => none enabled
    if not whitelist:
        try:
            from ..pvf.utils.log_event import log_event

            log_event("analytic tracking suppressed: whitelist empty (none enabled)", severity=1)
        except Exception:
            pass
        return None

    # Substitute all placeholder occurrences
    effective = script.replace(_PLACEHOLDER, token)

    # Whitelist: '*' allows all
    if len(whitelist) == 1 and whitelist[0].strip() == "*":
        return effective

    urls = _extract_urls(effective)
    for url in urls:
        if not _is_whitelisted_url(url, whitelist):
            try:
                from ..pvf.utils.log_event import log_event

                log_event(
                    f"analytic tracking suppressed: URL {url!r} not in whitelist {whitelist}",
                    severity=2,
                )
            except Exception:
                pass
            return None

    return effective
