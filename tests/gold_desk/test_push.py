"""تست Push — pure functions فقط."""

from __future__ import annotations

from src.gold_desk.push import PushMessage, PushSubscription


def test_subscription_to_dict():
    sub = PushSubscription(endpoint="https://example.com/sub", p256dh="abc", auth="xyz")
    d = sub.to_dict()
    assert d["endpoint"] == "https://example.com/sub"
    assert d["p256dh"] == "abc"
    assert d["auth"] == "xyz"


def test_message_to_dict():
    m = PushMessage(title="t", body="b", url="/gold", tag="alert")
    d = m.to_dict()
    assert d["title"] == "t"
    assert d["tag"] == "alert"


def test_message_defaults():
    m = PushMessage(title="t", body="b")
    assert m.url == "/gold"
    assert m.icon == "/icons/golddesk-192.png"
    assert m.tag is None
