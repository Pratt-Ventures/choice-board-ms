import json

from fastapi.testclient import TestClient

from src.pvf.utils.auth_tokens import create_access_token
from src.pvf.utils.webcalls_and_hooks import (
    APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY,
    APPLICATION_API_HEADER_SIGNATURE,
    WebrequestSignature,
)


def clear_auth(client: TestClient) -> None:
    client.cookies.clear()


def login(client: TestClient, email: str, password: str):
    clear_auth(client)
    return client.post("/auth-ws/login", json={"email": email, "password": password})


def as_user(client: TestClient, user_id: int) -> None:
    client.cookies.clear()
    client.cookies.set("access_token", create_access_token(user_id))


def signed_api_headers(body: dict | list | str | bytes, rq_key: str, shared_secret: str) -> dict[str, str]:
    if isinstance(body, (dict, list)):
        payload = json.dumps(body, separators=(",", ":"))
    elif isinstance(body, bytes):
        payload = body.decode("utf-8")
    else:
        payload = body
    signature = WebrequestSignature.generate_signed_payload_header(payload, shared_secret)
    return {
        APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY: rq_key,
        APPLICATION_API_HEADER_SIGNATURE: signature,
        "Content-Type": "application/json",
    }
