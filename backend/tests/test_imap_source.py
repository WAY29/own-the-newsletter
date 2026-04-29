import imaplib

import pytest

from app.imap_source import _IMAP_CLIENT_ID, ImapConfig, ImapSource, _ImapSession


class FakeImapClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.calls.append(("login", username, password))
        return "OK", [b"Logged in"]

    def xatom(self, name: str, *args: str) -> tuple[str, list[bytes]]:
        self.calls.append(("xatom", name, *args))
        return "OK", [b"ID completed"]

    def close(self) -> tuple[str, list[bytes]]:
        self.calls.append(("close",))
        return "OK", [b"Closed"]

    def logout(self) -> tuple[str, list[bytes]]:
        self.calls.append(("logout",))
        return "OK", [b"Logged out"]


def test_session_sends_imap_id_after_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeImapClient()

    def fake_ssl(host: str, port: int, timeout: int) -> FakeImapClient:
        client.calls.append(("connect_ssl", host, port, timeout))
        return client

    monkeypatch.setattr(imaplib, "IMAP4_SSL", fake_ssl)
    config = ImapConfig(
        host="imap.163.com",
        port=993,
        tls="ssl",
        username="user@163.com",
        password="authorization-code",
        folders=["INBOX"],
        timeout_seconds=15,
    )

    with _ImapSession(config):
        pass

    assert client.calls[:3] == [
        ("connect_ssl", "imap.163.com", 993, 15),
        ("login", "user@163.com", "authorization-code"),
        ("xatom", "ID", _IMAP_CLIENT_ID),
    ]


def test_session_ignores_servers_without_imap_id_support(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoIdClient(FakeImapClient):
        def xatom(self, name: str, *args: str) -> tuple[str, list[bytes]]:
            self.calls.append(("xatom", name, *args))
            raise imaplib.IMAP4.error("BAD unknown command")

    client = NoIdClient()

    def fake_ssl(host: str, port: int, timeout: int) -> NoIdClient:
        client.calls.append(("connect_ssl", host, port, timeout))
        return client

    monkeypatch.setattr(imaplib, "IMAP4_SSL", fake_ssl)
    config = ImapConfig(
        host="imap.example.test",
        port=993,
        tls="ssl",
        username="user@example.test",
        password="password",
        folders=["INBOX"],
    )

    with _ImapSession(config):
        pass

    assert ("logout",) in client.calls


def test_select_folder_error_includes_server_response() -> None:
    class SelectFailureClient:
        def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
            assert mailbox == '"INBOX"'
            assert readonly is True
            return "NO", [b"SELECT Unsafe Login. Please contact kefu@188.com for help"]

    with pytest.raises(RuntimeError, match="Unsafe Login"):
        ImapSource()._select_folder(SelectFailureClient(), "INBOX")  # pyright: ignore[reportArgumentType]
