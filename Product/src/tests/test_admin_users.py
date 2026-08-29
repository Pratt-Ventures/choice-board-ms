from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_user, uid


def test_user_create_as_admin(client, account):
    as_user(client, account.admin.id)
    email = f"{uid('nu')}@example.com"
    response = client.post(
        "/ws/user/user-create",
        json={
            "email": email,
            "name": "New PvfUser",
            "phone": "555-1000",
            "customer_admin": False,
            "password": uid("pw"),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    user_info = body.get("user_info") or {}
    if user_info.get("id"):
        account.tracked_user_ids.append(user_info["id"])


def test_user_create_non_admin_forbidden(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/user/user-create",
        json={
            "email": f"{uid('x')}@example.com",
            "name": "Nope",
            "password": "pw",
        },
    )
    assert response.status_code == 403


def test_user_create_unauthenticated(client):
    clear_auth(client)
    response = client.post(
        "/ws/user/user-create",
        json={"email": f"{uid('x')}@example.com", "name": "Nope", "password": "pw"},
    )
    assert response.status_code in (401, 403)


def test_customer_create_as_sysadmin(client, sysadmin_account):
    as_user(client, sysadmin_account.admin.id)
    email = f"{uid('cust')}@example.com"
    response = client.post(
        "/ws/user/customer-create",
        json={
            "customer_name": "Admin Created Co",
            "customer_email": email,
            "admin_email": email,
            "admin_name": "Admin",
            "admin_phone": "555-2000",
            "admin_password": uid("pw"),
            "customer_activated": True,
            "send_welcome_email": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    assert body.get("customer_id")


def test_customer_create_non_sysadmin_forbidden(client, account):
    as_user(client, account.admin.id)
    email = f"{uid('cust')}@example.com"
    response = client.post(
        "/ws/user/customer-create",
        json={
            "customer_name": "Blocked Co",
            "admin_email": email,
            "admin_name": "Admin",
            "admin_password": "pw",
        },
    )
    assert response.status_code == 403


def test_user_get_by_id_same_customer(client, account):
    as_user(client, account.admin.id)
    response = client.get(f"/ws/user/user-get-by-id?retrieve_by_id={account.member.id}")
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    assert body.get("user_info", {}).get("id") == account.member.id


def test_user_get_by_id_cross_tenant_denied(client, account, other_account):
    as_user(client, account.admin.id)
    response = client.get(f"/ws/user/user-get-by-id?retrieve_by_id={other_account.admin.id}")
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason") or body.get("user_info") is None


def test_user_get_by_email_same_customer(client, account):
    as_user(client, account.admin.id)
    response = client.get(f"/ws/user/user-get-by-email?retrieve_by_email={account.member_email}")
    assert response.status_code == 200
    body = response.json()
    assert body.get("user_info", {}).get("email") == account.member_email


def test_user_get_by_email_cross_tenant_denied(client, account, other_account):
    as_user(client, account.admin.id)
    response = client.get(
        f"/ws/user/user-get-by-email?retrieve_by_email={other_account.admin_email}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason") or body.get("user_info") is None


def test_user_update_self(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/user-update",
        json={"id": account.member.id, "name": "Updated Member Name"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)


def test_user_update_other_as_non_admin_forbidden(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/user-update",
        json={"id": account.admin.id, "name": "Hijack"},
    )
    assert response.status_code == 403


def test_user_update_escalate_admin_as_non_admin_forbidden(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/user-update",
        json={"id": account.member.id, "customer_admin": True},
    )
    assert response.status_code == 403


def test_user_delete_by_admin(client, account):
    user, _ = create_user(customer_id=account.customer.id, customer_admin=False)
    account.tracked_user_ids.append(user.id)
    as_user(client, account.admin.id)
    response = client.request("DELETE", "/ws/user/delete-user", json={"user_id": user.id})
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    assert body.get("user_id") == user.id


def test_user_delete_self_fails(client, account):
    as_user(client, account.admin.id)
    response = client.request(
        "DELETE", "/ws/user/delete-user", json={"user_id": account.admin.id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")


def test_user_delete_non_admin_forbidden(client, account):
    user, _ = create_user(customer_id=account.customer.id, customer_admin=False)
    account.tracked_user_ids.append(user.id)
    as_user(client, account.member.id)
    response = client.request("DELETE", "/ws/user/delete-user", json={"user_id": user.id})
    assert response.status_code == 403


def test_user_delete_cross_customer_fails(client, account, other_account):
    as_user(client, account.admin.id)
    response = client.request(
        "DELETE", "/ws/user/delete-user", json={"user_id": other_account.admin.id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")


def test_user_my_info(client, account):
    as_user(client, account.admin.id)
    response = client.get("/ws/user/user-my-info")
    assert response.status_code == 200
    body = response.json()
    assert body.get("user_info", {}).get("email") == account.admin_email


def test_user_my_info_unauthenticated(client):
    clear_auth(client)
    response = client.get("/ws/user/user-my-info")
    assert response.status_code in (401, 403)


def test_admin_sets_power_user_mode(client, account):
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/user-update",
        json={"id": account.member.id, "power_user_mode": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    check = client.get(f"/ws/user/user-get-by-id?retrieve_by_id={account.member.id}")
    assert check.status_code == 200
    assert check.json().get("user_info", {}).get("power_user_mode") == 2


def test_member_cannot_set_power_user_mode(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/user-update",
        json={"id": account.member.id, "power_user_mode": 2},
    )
    assert response.status_code == 403


def test_admin_create_user_with_power_mode(client, account):
    as_user(client, account.admin.id)
    email = f"{uid('pwr')}@example.com"
    response = client.post(
        "/ws/user/user-create",
        json={
            "email": email,
            "name": "Power Member",
            "password": uid("pw"),
            "customer_admin": False,
            "power_user_mode": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    user_info = body.get("user_info") or {}
    if user_info.get("id"):
        account.tracked_user_ids.append(user_info["id"])
    assert user_info.get("power_user_mode") == 1
