from src.tests.helpers.auth_client import as_user


def test_post_subscriber_transaction_as_sysadmin(client, sysadmin_account):
    as_user(client, sysadmin_account.admin.id)
    response = client.post(
        "/ws/admin/post-subscriber-transaction",
        json={
            "customer_id": sysadmin_account.customer.id,
            "transaction_type": "purchase+",
            "transaction_units": "months",
            "transaction_month_count": 1,
            "transaction_day_count": 0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    assert body.get("subscriber_transaction_id")


def test_post_subscriber_transaction_non_sysadmin_denied(client, account):
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/admin/post-subscriber-transaction",
        json={
            "customer_id": account.customer.id,
            "transaction_type": "purchase+",
            "transaction_units": "months",
            "transaction_month_count": 1,
            "transaction_day_count": 0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")
    assert "Unauthorized" in body["failure_reason"]
