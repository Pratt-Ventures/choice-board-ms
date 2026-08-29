import json

from src.config.config_settings import settings


def test_stripe_hook_unknown_hook_str(client):
    response = client.post(
        "/hook-stripe-events/not-a-real-hook-id",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=abc"},
    )
    assert response.status_code == 404


def test_stripe_hook_missing_signature(client):
    hook = settings.STRIPE_HOOK_STR_PRIMARY
    response = client.post(
        f"/hook-stripe-events/{hook}",
        content=b'{"id":"evt_test"}',
    )
    assert response.status_code in (200, 400, 401, 403, 422)
    if response.status_code == 200:
        assert response.json() is False


def test_stripe_hook_invalid_signature(client, mocker):
    hook = settings.STRIPE_HOOK_STR_PRIMARY

    class SigErr(Exception):
        pass

    mocker.patch("src.pvf.api.hook_stripe_events.stripe.error.SignatureVerificationError", SigErr)
    mocker.patch(
        "src.pvf.api.hook_stripe_events.stripe.Webhook.construct_event",
        side_effect=SigErr("bad sig"),
    )
    response = client.post(
        f"/hook-stripe-events/{hook}",
        content=b'{"id":"evt_test"}',
        headers={"stripe-signature": "t=1,v1=invalid"},
    )
    assert response.status_code == 200
    assert response.json() is False


def test_stripe_hook_happy_path_mocked(client, full_account, mocker):
    import uuid
    hook = settings.STRIPE_HOOK_STR_PRIMARY
    mock_event = {
        "object": "event",
        "id": f"evt_pytest_{uuid.uuid4().hex}",
        "type": "customer.updated",
        "livemode": False,
        "data": {"object": {"id": "cus_x", "object": "pvf_customer", "email": full_account.customer.customer_email}},
    }
    mocker.patch(
        "src.pvf.api.hook_stripe_events.stripe.Webhook.construct_event",
        return_value=mock_event,
    )
    response = client.post(
        f"/hook-stripe-events/{hook}",
        content=json.dumps(mock_event).encode(),
        headers={"stripe-signature": "t=1,v1=mock"},
    )
    assert response.status_code == 200
    assert response.json() is True


def test_stripe_sandbox_hook_unknown(client):
    response = client.post(
        "/hook-stripe-events-sandbox/not-a-real-hook-id",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=abc"},
    )
    assert response.status_code == 404
