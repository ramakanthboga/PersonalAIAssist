"""Unit tests for registration email validation."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.security.email_validation import normalize_email, validate_registration_email


def test_normalize_email():
    assert normalize_email("  User@Gmail.COM ") == "user@gmail.com"


def test_rejects_example_com():
    with pytest.raises(ValidationError):
        validate_registration_email("user@example.com")


def test_rejects_local_tld():
    with pytest.raises(ValidationError):
        validate_registration_email("user@company.local")


def test_rejects_disposable():
    with pytest.raises(ValidationError):
        validate_registration_email("a@mailinator.com")


def test_rejects_malformed():
    with pytest.raises(ValidationError):
        validate_registration_email("not-an-email")


@pytest.mark.parametrize(
    "address",
    [
        "Person@Gmail.com",
        "user@hotmail.com",
        "user@outlook.com",
        "user@live.com",
        "user@yahoo.com",
        "user@icloud.com",
        "user@proton.me",
    ],
)
def test_accepts_trusted_providers_without_dns(address, monkeypatch):
    # Even if DNS fails, trusted providers must still register.
    monkeypatch.setattr(
        "app.security.email_validation._has_dns_mail_records",
        lambda _domain: False,
    )
    assert validate_registration_email(address) == address.lower()


def test_accepts_custom_domain_with_mx(monkeypatch):
    monkeypatch.setattr(
        "app.security.email_validation._has_dns_mail_records",
        lambda _domain: True,
    )
    assert validate_registration_email("me@mycompany.org") == "me@mycompany.org"


def test_rejects_unknown_when_no_dns(monkeypatch):
    monkeypatch.setattr(
        "app.security.email_validation._has_dns_mail_records",
        lambda _domain: False,
    )
    with pytest.raises(ValidationError, match="could not be verified"):
        validate_registration_email("user@some-random-domain-xyz.com")
