import hmac
import json
import time
from typing import cast
from collections import OrderedDict
from hashlib import sha256

from .utils_show import show_vars

APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY = 'X-api-request-authentication'
APPLICATION_API_HEADER_SIGNATURE = 'X-api-request-signature'
DEFAULT_SIGNATURE_TIME_TOLERANCE = 300  # 5 minutes

class WebhookSignatureError(Exception):
    pass

class SignatureVerificationError(WebhookSignatureError):
    pass

class SignatureVerificationMismatchError(SignatureVerificationError):
    pass

class SignatureVerificationToleranceError(SignatureVerificationError):
    pass


class Webrequest(object):
    DEFAULT_TOLERANCE = 300  # 5 minutes

    @staticmethod
    def construct_event(
        payload, sig_header, secret, tolerance=DEFAULT_TOLERANCE, api_key=None, return_payload=True, api_config_id='Not-Specified', test_environment=False, force_decode=False
    ):
        if force_decode or hasattr(payload, "decode"):
            payload = payload.decode("utf-8")

        WebrequestSignature.verify_header(payload, sig_header, secret, tolerance, api_config_id=api_config_id, test_environment=test_environment)
        data = json.loads(payload, object_pairs_hook=OrderedDict) if return_payload else None
        return data


class WebrequestSignature(object):
    EXPECTED_SCHEME = "v1"

    @staticmethod
    def _compute_signature(payload, secret):
        mac = hmac.new(
            secret.encode("utf-8"),
            msg=payload.encode("utf-8"),
            digestmod=sha256,
        )
        return mac.hexdigest()

    @staticmethod
    def _get_timestamp_and_signatures(header, scheme):
        list_items = [i.split("=", 2) for i in header.split(",")]
        timestamp = int(float([i[1].strip() for i in list_items if i[0].strip() == "t"][0]))
        signatures = [i[1].strip() for i in list_items if i[0].strip() == scheme]
        return timestamp, signatures

    @classmethod
    def generate_signed_payload_header(cls, payload, secret, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        signed_payload = "%d.%s" % (timestamp, payload)
        signature = WebrequestSignature._compute_signature(signed_payload, secret)
        return f"t={timestamp:.1f}, {cls.EXPECTED_SCHEME}={signature}"
    
    @classmethod
    def verify_header(cls, payload, header, secret, tolerance=None, api_config_id='Not-Specified', test_environment=False):
        try:
            timestamp, signatures = cls._get_timestamp_and_signatures(
                header, cls.EXPECTED_SCHEME
            )
        except Exception as ex_info:
            raise SignatureVerificationError(
                "Unable to extract timestamp and signatures from header",
            )

        if not signatures:
            raise SignatureVerificationError(
                "No signatures found with expected scheme "
                "%s" % cls.EXPECTED_SCHEME,
            )

        cur_time = time.time()
        if tolerance and timestamp < cur_time - tolerance or timestamp > cur_time + tolerance:
            if test_environment:
                show_vars('webcalls_and_hooks.verify_header', Api_Config_Key=api_config_id, Expected_timestamp=int(time.time()) - 1, Received_timestamp=timestamp)
            raise SignatureVerificationToleranceError(
                "Timestamp outside the tolerance zone (%d)" % timestamp,
            )

        signed_payload = "%d.%s" % (timestamp, payload)
        expected_sig = cls._compute_signature(signed_payload, secret)
        if not any(secure_compare(expected_sig, s) for s in signatures):
            if test_environment:
                show_vars('webcalls_and_hooks.verify_header', Api_Config_Key=api_config_id, Expected_signature=expected_sig, Received_signatures=signatures)
            raise SignatureVerificationMismatchError(
                "No signatures found matching the expected signature for "
                "payload",
            )

        return True

def secure_compare(val1, val2):
    """
    Returns True if the two strings are equal, False otherwise.
    The time taken is independent of the number of characters that match.
    For the sake of simplicity, this function executes in constant time
    only when the two strings have the same length. It short-circuits when
    they have different lengths.
    """
    if len(val1) != len(val2):
        return False
    result = 0
    if isinstance(val1, bytes) and isinstance(val2, bytes):
        for x, y in zip(val1, val2):
            result |= x ^ y
    else:
        for x, y in zip(val1, val2):
            result |= ord(cast(str, x)) ^ ord(cast(str, y))
    return result == 0
