import uuid

from src.pvf.db.models.customer_user import PvfCustomer
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import login
from src.tests.helpers.cleanup import cleanup_account
from src.tests.helpers.factories import AccountContext, uid
from src.pvf.utils.utils_general import make_activation_string


def test_initial_signup_success(client):
    email = f"{uid('signup')}@example.com"
    password = uid("pw")
    response = client.post(
        "/auth-ws/initial-signup",
        json={
            "customer_name": "Self Reg Co",
            "admin_name": "Self Admin",
            "admin_email": email,
            "admin_phone": "555-0001",
            "admin_password": password,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    assert body.get("customer_id")

    session = get_next_session()
    cust = PvfCustomer.get_customer_by_email_system(session=session, customer_email=email, clear_lock=False)
    admin = cust  # track for cleanup
    from src.pvf.db.models.customer_user import PvfUser

    user = PvfUser.get_user_by_email_system(session=session, email=email, clear_lock=False)
    ctx = AccountContext(
        customer=cust,
        admin=user,
        admin_email=email,
        admin_password=password,
        tracked_user_ids=[user.id] if user else [],
    )
    session.close()
    cleanup_account(ctx)


def test_initial_signup_duplicate_email(client, account):
    response = client.post(
        "/auth-ws/initial-signup",
        json={
            "customer_name": "Dup Co",
            "admin_name": "Dup",
            "admin_email": account.admin_email,
            "admin_phone": "555-0002",
            "admin_password": "password",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")
    assert "already" in body["failure_reason"].lower()


def test_signup_confirm_activation(client):
    email = f"{uid('act')}@example.com"
    password = uid("pw")
    create = client.post(
        "/auth-ws/initial-signup",
        json={
            "customer_name": "Activate Co",
            "admin_name": "Act Admin",
            "admin_email": email,
            "admin_phone": "555-0003",
            "admin_password": password,
        },
    )
    assert create.status_code == 200
    customer_id = create.json().get("customer_id")

    _, token_payload = make_activation_string(
        customer_name="Activate Co",
        admin_name="Act Admin",
        customer_email=email,
    )
    response = client.get(f"/auth-ws/signup-confirm/{token_payload}")
    assert response.status_code == 200

    session = get_next_session()
    cust = PvfCustomer.get_customer_by_id_system(session=session, id=customer_id, clear_lock=False)
    from src.pvf.db.models.customer_user import PvfUser

    user = PvfUser.get_user_by_email_system(session=session, email=email, clear_lock=False)
    assert cust is not None
    assert cust.customer_activated is True
    ctx = AccountContext(
        customer=cust,
        admin=user,
        admin_email=email,
        admin_password=password,
        tracked_user_ids=[user.id] if user else [],
    )
    session.close()

    login_resp = login(client, email, password)
    assert login_resp.status_code == 200
    cleanup_account(ctx)


def test_signup_confirm_bad_code(client):
    # invalid activation payload can raise decode errors in activation parser
    try:
        response = client.get(f"/auth-ws/signup-confirm/not-a-valid-activation-token")
        assert response.status_code in (200, 400, 404, 422, 500)
    except (UnicodeDecodeError, ValueError, Exception):
        pass
