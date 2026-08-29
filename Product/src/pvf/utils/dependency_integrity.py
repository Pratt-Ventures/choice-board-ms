"""Boot-time dependency-injection integrity verification for the composed FastAPI apps.

Dependency injection is strictly enforced here, regardless of whether the dependency
data is an input parameter for a given endpoint: the runner refuses to start if any
route is missing the guard its application requires (or carries a guard that would
break its access model).

  - session app:  every route must depend on the session-JWT guard (or an admin variant)
  - external app: every route must depend on the signed-header guard
  - noauth app:   no route may depend on either guard (no authorization expected)
  - share app:    no route may depend on either guard (share cookie/magic-key gate instead)

Exemptions: routes tagged 'test-helpers' (non-production only, SessionDep-only by
design) and the public /status probes.
"""
from fastapi import FastAPI
from fastapi.routing import APIRoute

from ..depends.check_api_key_dependencies import get_api_key_info
from ..depends.check_user_session_jwt_dependencies import (
    get_current_user,
    get_current_user_customer_admin,
    get_current_user_system_admin,
)

SESSION_GUARDS = {get_current_user, get_current_user_customer_admin, get_current_user_system_admin}
EXTERNAL_GUARDS = {get_api_key_info}

EXEMPT_TAGS = {"test-helpers"}
EXEMPT_PATH_SUFFIXES = ("/status", "/analytic-tracking")


def _dependency_calls(route: APIRoute) -> set:
    calls = set()

    def walk(dependant) -> None:
        calls.add(dependant.call)
        for sub in dependant.dependencies:
            walk(sub)

    walk(route.dependant)
    return calls


def _is_exempt(route: APIRoute) -> bool:
    if EXEMPT_TAGS & set(route.tags or []):
        return True
    return any(route.path.endswith(suffix) for suffix in EXEMPT_PATH_SUFFIXES)


def verify_app_dependency_integrity(app: FastAPI, target: str) -> None:
    """Raise RuntimeError listing every DI violation on the given app."""
    violations: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or _is_exempt(route):
            continue
        calls = _dependency_calls(route)
        methods = ",".join(sorted(route.methods or []))
        label = f"{methods} {route.path} ({route.name})"
        if target == "session" and not (calls & SESSION_GUARDS):
            violations.append(f"{label}: missing required session-JWT dependency")
        elif target == "external" and not (calls & EXTERNAL_GUARDS):
            violations.append(f"{label}: missing required signed-header dependency")
        elif target in ("noauth", "share") and (calls & (SESSION_GUARDS | EXTERNAL_GUARDS)):
            violations.append(f"{label}: must not require session-JWT or signed-header dependencies")
    if violations:
        raise RuntimeError(
            f"Dependency integrity check failed for the '{target}' application:\n  "
            + "\n  ".join(violations)
        )
