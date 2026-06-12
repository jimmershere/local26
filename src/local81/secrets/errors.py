"""Typed errors for secret resolution.

The split matters at the call site: a *syntax* error is the operator's typo and
should fail plan validation loudly; a *not-found* or *forbidden* error means the
reference is well-formed but the backend cannot satisfy it, which must fail fast
at apply time rather than silently injecting an empty value.
"""

from __future__ import annotations

from local81.errors import Local81Error


class SecretError(Local81Error):
    """Base class for every secret-resolution failure."""


class SecretRefSyntaxError(SecretError):
    """The reference string is malformed (bad scheme, missing key fragment)."""


class SecretNotFoundError(SecretError):
    """The reference is well-formed but the backend holds no such value."""


class SecretForbiddenError(SecretError):
    """The backend refused access to the value (e.g. a 403 from OpenBao)."""


class SecretBackendError(SecretError):
    """The backend could not be reached or the helper tool is unavailable."""
