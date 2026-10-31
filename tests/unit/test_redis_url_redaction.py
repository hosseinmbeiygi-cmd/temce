from core.security.redaction import redact_redis_url


def test_password_only_url_is_redacted():
    assert (
        redact_redis_url("redis://:s3cret@127.0.0.1:16379/0")
        == "redis://:***@127.0.0.1:16379/0"
    )


def test_user_and_password_url_is_redacted():
    assert (
        redact_redis_url("redis://app:s3cret@redis.internal:6379/2")
        == "redis://app:***@redis.internal:6379/2"
    )


def test_ipv6_host_and_tls_scheme_are_preserved():
    assert (
        redact_redis_url("rediss://:s3cret@[::1]:6379/0")
        == "rediss://:***@[::1]:6379/0"
    )


def test_url_without_credentials_is_unchanged():
    assert redact_redis_url("redis://127.0.0.1:6379/0") == "redis://127.0.0.1:6379/0"


def test_malformed_or_empty_values_never_echo_the_input():
    for value in ("", "not-a-url", "redis://:s3cret", "redis://:s3cret@"):
        assert redact_redis_url(value) == "redis://***"
