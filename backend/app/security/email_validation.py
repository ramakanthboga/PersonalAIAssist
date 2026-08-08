"""Validate registration emails: format, blocklist, trusted providers, DNS MX/A."""

from __future__ import annotations

import re

import dns.exception
import dns.resolver

from app.core.exceptions import ValidationError

_EMAIL_RE = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)

# Well-known consumer / work inboxes — always allowed for password signup.
# (Skips DNS MX so registration works inside Docker with restricted DNS.)
_TRUSTED_DOMAINS = frozenset(
    {
        # Google
        "gmail.com",
        "googlemail.com",
        # Microsoft
        "hotmail.com",
        "hotmail.co.uk",
        "hotmail.fr",
        "hotmail.de",
        "hotmail.it",
        "outlook.com",
        "outlook.in",
        "live.com",
        "live.co.uk",
        "msn.com",
        # Yahoo
        "yahoo.com",
        "yahoo.co.in",
        "yahoo.co.uk",
        "ymail.com",
        "rocketmail.com",
        # Apple
        "icloud.com",
        "me.com",
        "mac.com",
        # Others common for personal accounts
        "aol.com",
        "proton.me",
        "protonmail.com",
        "zoho.com",
        "gmx.com",
        "gmx.net",
        "mail.com",
        "rediffmail.com",
    }
)

# Placeholder / disposable / clearly non-deliverable domains for password signup.
_BLOCKED_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "test.org",
        "invalid",
        "localhost",
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.org",
        "10minutemail.com",
        "tempmail.com",
        "temp-mail.org",
        "throwaway.email",
        "yopmail.com",
        "sharklasers.com",
        "trashmail.com",
        "fakeinbox.com",
        "getnada.com",
        "dispostable.com",
        "maildrop.cc",
        "mailnesia.com",
    }
)

_BLOCKED_SUFFIXES = (
    ".local",
    ".invalid",
    ".test",
    ".example",
    ".localhost",
    ".internal",
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1]


def _has_dns_mail_records(domain: str) -> bool:
    """True if the domain has MX records, or an A/AAAA fallback."""
    resolver = dns.resolver.Resolver(configure=True)
    # Prefer public resolvers when container DNS cannot resolve MX.
    resolver.nameservers = ["8.8.8.8", "1.1.1.1", *list(resolver.nameservers or [])]
    resolver.lifetime = 5.0
    resolver.timeout = 3.0

    try:
        answers = resolver.resolve(domain, "MX")
        if answers:
            return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        pass
    except dns.exception.DNSException:
        pass

    for rdtype in ("A", "AAAA"):
        try:
            answers = resolver.resolve(domain, rdtype)
            if answers:
                return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            continue
        except dns.exception.DNSException:
            return False
    return False


def validate_registration_email(email: str) -> str:
    """Normalize and validate an email for password registration.

    Accepts Gmail, Hotmail/Outlook, Yahoo, and other real inboxes.
    Rejects disposable / placeholder domains.

    Raises:
        ValidationError: if the address is malformed, blocked, or unverifiable.
    """
    normalized = normalize_email(email)
    if not normalized or not _EMAIL_RE.match(normalized):
        raise ValidationError("Enter a valid email address")

    domain = _domain_of(normalized)
    if domain in _BLOCKED_DOMAINS or any(domain.endswith(suf) for suf in _BLOCKED_SUFFIXES):
        raise ValidationError(
            "That email domain is not allowed. Use Gmail, Hotmail, Outlook, Yahoo, "
            "or another real inbox — or Continue with Google."
        )

    labels = domain.split(".")
    if len(labels) < 2 or len(labels[-1]) < 2:
        raise ValidationError("Enter a valid email address with a real domain")

    # Trusted consumer domains: allow without DNS (works offline / in Docker).
    if domain in _TRUSTED_DOMAINS:
        return normalized

    if not _has_dns_mail_records(domain):
        raise ValidationError(
            "That email domain could not be verified. Use Gmail, Hotmail, Outlook, "
            "Yahoo, or another real inbox — or Continue with Google."
        )

    return normalized
