"""Workspace and project branding image upload / access control / compression."""
from io import BytesIO

import numpy as np
from PIL import Image

from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_project, uid
from src.pvf.utils.branding_image import MAX_BRANDING_STORED_BYTES, MAX_BRANDING_UPLOAD_BYTES


def _png_bytes(width: int = 32, height: int = 32, color=(30, 120, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _noisy_png_over_1mb() -> bytes:
    """Incompressible-ish RGB noise so PNG exceeds the 1MB storage target."""
    rng = np.random.default_rng(42)
    # 1200x1200 RGB noise is typically several MB as PNG
    arr = rng.integers(0, 256, size=(1200, 1200, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    buf = BytesIO()
    img.save(buf, format="PNG", compress_level=0)
    data = buf.getvalue()
    assert len(data) > MAX_BRANDING_STORED_BYTES
    assert len(data) <= MAX_BRANDING_UPLOAD_BYTES
    return data


_PNG = _png_bytes()


def _create_share(client, user_id: int, project_id: int, **overrides) -> dict:
    as_user(client, user_id)
    body = {
        "shared_type": "vote",
        "shared_entity_db_id": project_id,
        "access_mode": "open_access",
        "link_auto_send": False,
        "share_link_name": f"brand-{uid()}",
        "shared_with_email": f"{uid('rcpt')}@example.com",
        "shared_with_person_name": "Guest",
    }
    body.update(overrides)
    response = client.post("/ws/create-share-link", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result.get("failure_reason"), result
    clear_auth(client)
    return result["link_info"]


def test_customer_branding_upload_get_delete(client, account):
    as_user(client, account.admin.id)
    meta = client.get("/ws/branding/customer-meta")
    assert meta.status_code == 200
    assert meta.json().get("has_image") is False

    up = client.post(
        "/ws/branding/customer-image",
        files={"file": ("logo.png", BytesIO(_PNG), "image/png")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert not body.get("failure_reason"), body
    assert body.get("has_image") is True
    assert body.get("byte_size") == len(_PNG)
    assert body.get("original_byte_size") == len(_PNG)
    assert body.get("original_file_name") == "logo.png"
    assert body.get("file_name") == "logo.png"
    assert body.get("was_compressed") is False
    assert body.get("content_type") == "image/png"

    img = client.get("/ws/branding/customer-image")
    assert img.status_code == 200
    assert img.headers.get("content-type", "").startswith("image/png")
    assert img.content == _PNG

    deleted = client.delete("/ws/branding/customer-image")
    assert deleted.status_code == 200
    assert deleted.json().get("has_image") is False
    assert client.get("/ws/branding/customer-image").status_code == 404


def test_customer_branding_non_admin_denied(client, account):
    as_user(client, account.member.id)
    up = client.post(
        "/ws/branding/customer-image",
        files={"file": ("logo.png", BytesIO(_PNG), "image/png")},
    )
    assert up.status_code == 200
    assert up.json().get("failure_reason")


def test_customer_branding_unauthenticated_download_denied(client, account):
    as_user(client, account.admin.id)
    client.post(
        "/ws/branding/customer-image",
        files={"file": ("logo.png", BytesIO(_PNG), "image/png")},
    )
    clear_auth(client)
    assert client.get("/ws/branding/customer-image").status_code in (401, 403)
    assert client.get("/ws/branding/customer-meta").status_code in (401, 403)


def test_customer_branding_too_large_upload(client, account):
    as_user(client, account.admin.id)
    big = b"\x89PNG\r\n\x1a\n" + b"x" * (MAX_BRANDING_UPLOAD_BYTES)
    up = client.post(
        "/ws/branding/customer-image",
        files={"file": ("big.png", BytesIO(big), "image/png")},
    )
    assert up.status_code == 400


def test_customer_branding_compresses_large_image(client, account):
    as_user(client, account.admin.id)
    raw = _noisy_png_over_1mb()

    up = client.post(
        "/ws/branding/customer-image",
        files={"file": ("path/to/Company Logo.png", BytesIO(raw), "image/png")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert not body.get("failure_reason"), body
    assert body.get("has_image") is True
    assert body.get("was_compressed") is True
    assert body.get("original_file_name") == "Company Logo.png"
    assert body.get("file_name") == "Company Logo.png"
    assert body.get("original_byte_size") == len(raw)
    assert body.get("byte_size") <= MAX_BRANDING_STORED_BYTES
    assert body.get("byte_size") < body.get("original_byte_size")

    img = client.get("/ws/branding/customer-image")
    assert img.status_code == 200
    assert len(img.content) == body.get("byte_size")
    assert len(img.content) <= MAX_BRANDING_STORED_BYTES


def test_customer_branding_cross_tenant_download(client, account, other_account):
    as_user(client, account.admin.id)
    up = client.post(
        "/ws/branding/customer-image",
        files={"file": ("logo.png", BytesIO(_PNG), "image/png")},
    )
    assert up.status_code == 200
    assert not up.json().get("failure_reason")

    # Other tenant session only sees their own (empty) branding — not account's bytes
    as_user(client, other_account.admin.id)
    img = client.get("/ws/branding/customer-image")
    assert img.status_code == 404
    meta = client.get("/ws/branding/customer-meta")
    assert meta.status_code == 200
    assert meta.json().get("has_image") is False


def test_project_branding_upload_get_delete(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)

    up = client.post(
        "/ws/branding/project-image",
        data={"project_id": str(project.id)},
        files={"file": ("p.png", BytesIO(_PNG), "image/png")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert not body.get("failure_reason"), body
    assert body.get("has_image") is True
    assert body.get("original_file_name") == "p.png"
    assert body.get("was_compressed") is False

    meta = client.get("/ws/branding/project-meta", params={"project_id": project.id})
    assert meta.status_code == 200
    assert meta.json().get("has_image") is True
    assert meta.json().get("original_byte_size") == len(_PNG)

    img = client.get("/ws/branding/project-image", params={"project_id": project.id})
    assert img.status_code == 200
    assert img.content == _PNG

    deleted = client.delete("/ws/branding/project-image", params={"project_id": project.id})
    assert deleted.status_code == 200
    assert client.get("/ws/branding/project-image", params={"project_id": project.id}).status_code == 404


def test_project_branding_cross_tenant(client, account, other_account):
    project = create_project(account)
    as_user(client, account.admin.id)
    up = client.post(
        "/ws/branding/project-image",
        data={"project_id": str(project.id)},
        files={"file": ("p.png", BytesIO(_PNG), "image/png")},
    )
    assert up.status_code == 200
    assert not up.json().get("failure_reason")

    as_user(client, other_account.admin.id)
    meta = client.get("/ws/branding/project-meta", params={"project_id": project.id})
    assert meta.status_code == 200
    assert meta.json().get("failure_reason") or meta.json().get("has_image") is False
    img = client.get("/ws/branding/project-image", params={"project_id": project.id})
    assert img.status_code == 404


def test_share_image_requires_authenticated_share_session(client, account):
    """Binary branding on share requires share cookie; token alone is not enough."""
    project = create_project(account)
    as_user(client, account.admin.id)
    client.post(
        "/ws/branding/customer-image",
        files={"file": ("logo.png", BytesIO(_PNG), "image/png")},
    )
    client.post(
        "/ws/branding/project-image",
        data={"project_id": str(project.id)},
        files={"file": ("p.png", BytesIO(_PNG), "image/png")},
    )
    clear_auth(client)

    plain = "Share-Secret-99"
    link = _create_share(
        client,
        account.admin.id,
        project.id,
        access_mode="password_only",
        share_password=plain,
    )
    token = link["magic_token"]

    clear_auth(client)
    # Meta allowed with valid share token (no binary)
    meta = client.get(f"/ext-ws/share/{token}/branding")
    assert meta.status_code == 200, meta.text
    branding = meta.json().get("branding") or {}
    assert branding.get("customer_name") == account.customer.customer_name
    assert branding.get("has_customer_image") is True
    assert branding.get("has_project_image") is True

    # Without share session cookie → denied
    cimg = client.get(f"/ext-ws/share/{token}/customer-image")
    assert cimg.status_code == 401
    pimg = client.get(f"/ext-ws/share/{token}/project-image")
    assert pimg.status_code == 401

    # Wrong password still no cookie / no image
    denied = client.post(
        f"/ext-ws/share/{token}/vote",
        json={"display_name": "G", "verification_password": "nope"},
    )
    assert denied.status_code == 200
    assert denied.json().get("failure_reason")
    assert client.get(f"/ext-ws/share/{token}/customer-image").status_code == 401

    # Authenticate share → cookie set → images allowed
    ok = client.post(
        f"/ext-ws/share/{token}/vote",
        json={"display_name": "Guest", "verification_password": plain},
    )
    assert ok.status_code == 200, ok.text
    assert not ok.json().get("failure_reason"), ok.json()
    proj = ok.json().get("project") or {}
    assert proj.get("has_customer_branding_image") is True
    assert proj.get("has_project_branding_image") is True

    cimg2 = client.get(f"/ext-ws/share/{token}/customer-image")
    assert cimg2.status_code == 200
    assert cimg2.content == _PNG
    pimg2 = client.get(f"/ext-ws/share/{token}/project-image")
    assert pimg2.status_code == 200
    assert pimg2.content == _PNG


def test_share_branding_open_access_after_unlock(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    client.post(
        "/ws/branding/customer-image",
        files={"file": ("logo.png", BytesIO(_PNG), "image/png")},
    )
    clear_auth(client)

    link = _create_share(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]
    clear_auth(client)

    assert client.get(f"/ext-ws/share/{token}/customer-image").status_code == 401

    vote = client.post(
        f"/ext-ws/share/{token}/vote",
        json={"display_name": "Guest", "verification_email": "g@example.com"},
    )
    assert vote.status_code == 200, vote.text
    assert client.get(f"/ext-ws/share/{token}/customer-image").status_code == 200


def test_share_branding_invalid_token(client):
    clear_auth(client)
    meta = client.get("/ext-ws/share/not-a-real-token/branding")
    assert meta.status_code == 200
    assert meta.json().get("failure_reason")
    assert client.get("/ext-ws/share/not-a-real-token/customer-image").status_code in (401, 404)
