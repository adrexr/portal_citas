"""Contracts for receiving and persisting WhatsApp Cloud API messages."""

import hashlib
import hmac
import unittest

from api.whatsapp_webhook import extract_incoming_messages, is_valid_signature, verify_webhook_request


class WhatsAppWebhookTests(unittest.TestCase):
    def test_verifies_the_meta_handshake_with_the_configured_token(self) -> None:
        challenge = verify_webhook_request(
            {"hub.mode": ["subscribe"], "hub.verify_token": ["token-seguro"], "hub.challenge": ["abc123"]},
            "token-seguro",
        )

        self.assertEqual(challenge, "abc123")

    def test_rejects_an_invalid_meta_handshake(self) -> None:
        challenge = verify_webhook_request(
            {"hub.mode": ["subscribe"], "hub.verify_token": ["incorrecto"], "hub.challenge": ["abc123"]},
            "token-seguro",
        )

        self.assertIsNone(challenge)

    def test_validates_the_meta_signature_before_processing_a_message(self) -> None:
        body = b'{"object":"whatsapp_business_account"}'
        valid_signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()

        self.assertTrue(is_valid_signature(body, valid_signature, "app-secret"))
        self.assertFalse(is_valid_signature(body, "sha256=incorrecta", "app-secret"))

    def test_extracts_text_message_without_retaining_full_provider_payload(self) -> None:
        messages = extract_incoming_messages({
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": "12345"},
                "messages": [{
                    "id": "wamid.abc", "from": "573001234567", "timestamp": "1791345600",
                    "type": "text", "text": {"body": "Hola, quiero una cita"},
                }],
            }}]}],
        })

        self.assertEqual(messages, [{
            "provider_message_id": "wamid.abc",
            "sender_phone": "573001234567",
            "recipient_phone_number_id": "12345",
            "message_type": "text",
            "message_text": "Hola, quiero una cita",
            "sent_at": "2026-10-07T04:00:00+00:00",
        }])

    def test_ignores_status_updates_and_malformed_messages(self) -> None:
        self.assertEqual(extract_incoming_messages({"entry": [{"changes": [{"value": {
            "statuses": [{"id": "wamid.status"}],
            "messages": [{"id": "", "from": "57300", "type": "text"}],
        }}]}]}), [])


if __name__ == "__main__":
    unittest.main()
