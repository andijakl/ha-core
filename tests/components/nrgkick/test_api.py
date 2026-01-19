"""Tests for the NRGkick exceptions."""

from __future__ import annotations

from homeassistant.components.nrgkick.api import (
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.exceptions import HomeAssistantError


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_exception_inheritance(self):
        """Test HA exceptions inherit from HomeAssistantError."""
        assert issubclass(NRGkickApiClientError, HomeAssistantError)
        assert issubclass(NRGkickApiClientCommunicationError, NRGkickApiClientError)
        assert issubclass(NRGkickApiClientAuthenticationError, NRGkickApiClientError)

    def test_exception_translation_keys(self):
        """Test exceptions have translation keys."""
        assert NRGkickApiClientError.translation_domain == "nrgkick"
        assert (
            NRGkickApiClientCommunicationError.translation_key == "communication_error"
        )
        assert (
            NRGkickApiClientAuthenticationError.translation_key
            == "authentication_error"
        )
