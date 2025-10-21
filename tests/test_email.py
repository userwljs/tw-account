import email
import time
from typing import Optional

from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from aiosmtpd.smtp import Envelope


class SMTPHandlerForTesting(Message):
    def __init__(self):
        self.envelope: Optional[Envelope] = None

        super().__init__()

    def handle_DATA(self, server, session, envelope):
        self.envelope = envelope

        return "250 Message accepted for delivery"

    def handle_message(self, message):
        return "250 OK"


def test_get_email_domain_restriction_info(test_client_with_config):
    test_client = test_client_with_config[0]
    response = test_client.get("/email/domain_restriction_info")
    assert response.status_code == 200
    assert response.json() == {
        "restrict_email_domains": "whitelist",
        "restricted_email_domains": ["example.com"],
    }


def test_send_email_verification_code(test_client_with_config, monkeypatch):
    test_client = test_client_with_config[0]
    config = test_client_with_config[1]
    handler = SMTPHandlerForTesting()
    controller = Controller(handler, port=9901)
    controller.start()

    response = test_client.post(
        "/email/send_verification_code", json={"email": "receiver@example.com"}
    )
    time.sleep(0.1)
    assert response.status_code == 202

    controller.stop()

    assert handler.envelope is not None
    assert handler.envelope.mail_from == "noreply@example.com"
    assert handler.envelope.rcpt_tos == ["receiver@example.com"]
    assert "TTTTTT" in email.message_from_bytes(handler.envelope.content).get_payload(
        decode=True
    ).decode(errors="replace")

    handler = SMTPHandlerForTesting()
    controller = Controller(handler, port=9901)
    controller.start()

    with monkeypatch.context() as m:
        m.setattr(config, "restrict_email_domains", "no")
        m.setattr(config, "email_verification_code_alphabet", "E")

        response = test_client.post(
            "/email/send_verification_code", json={"email": "receiver@outlook.com"}
        )
    time.sleep(0.1)
    assert response.status_code == 202

    controller.stop()

    assert handler.envelope is not None
    assert handler.envelope.mail_from == "noreply@example.com"
    assert handler.envelope.rcpt_tos == ["receiver@outlook.com"]
    assert "EEEEEE" in email.message_from_bytes(handler.envelope.content).get_payload(
        decode=True
    ).decode(errors="replace")


def test_email_domain_restriction(test_client_with_config, monkeypatch):
    test_client = test_client_with_config[0]
    config = test_client_with_config[1]

    with monkeypatch.context() as m:
        m.setattr(config, "restrict_email_domains", "whitelist")
        m.setattr(config, "restricted_email_domains", {"example.com"})
        response = test_client.post(
            "/email/send_verification_code", json={"email": "receiver@forbidden.com"}
        )
        assert response.status_code == 400

    with monkeypatch.context() as m:
        m.setattr(config, "restrict_email_domains", "blacklist")
        m.setattr(config, "restricted_email_domains", {"forbidden.com"})
        response = test_client.post(
            "/email/send_verification_code", json={"email": "receiver@forbidden.com"}
        )
        assert response.status_code == 400
