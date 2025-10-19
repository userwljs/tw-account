import email
import time
from typing import Optional

from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from aiosmtpd.smtp import Envelope
from fastapi.testclient import TestClient


class SMTPHandlerForTesting(Message):
    def __init__(self):
        self.envelope: Optional[Envelope] = None
        self.controller: Controller = None

        super().__init__()

    def handle_DATA(self, server, session, envelope):
        if self.controller is not None:
            self.controller.stop()

        self.envelope = envelope

        return "250 Message accepted for delivery"

    def handle_message(self, message):
        return "250 OK"


def test_get_email_domain_restriction_info(test_client: TestClient):
    response = test_client.get("/email/domain_restriction_info")
    assert response.status_code == 200
    assert response.json() == {
        "restrict_email_domains": "whitelist",
        "restricted_email_domains": ["example.com"],
    }


def test_send_email_verification_code(test_client: TestClient):
    handler = SMTPHandlerForTesting()
    controller = Controller(handler, port=9901)
    controller.start()

    response = test_client.post(
        "/email/send_verification_code", json={"email": "receiver@example.com"}
    )
    time.sleep(0.1)
    assert response.status_code == 202

    try:
        controller.stop()
    except AssertionError:
        pass

    assert handler.envelope is not None
    assert handler.envelope.mail_from == "noreply@example.com"
    assert handler.envelope.rcpt_tos == ["receiver@example.com"]
    assert "TTTTTT" in email.message_from_bytes(handler.envelope.content).get_payload(
        decode=True
    ).decode(errors="replace")
