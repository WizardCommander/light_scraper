"""Unit tests for Vibia authentication module.

Following CLAUDE.md: unit tests for pure logic, integration tests for I/O.
"""

import pytest
from src.auth.vibia_auth import VibiaAuth


class TestBuildDocumentRequest:
    """Unit tests for _build_document_request method."""

    def test_manual_request_without_family_id(self):
        """Should build manual request without familyId when not provided."""
        auth = VibiaAuth(email="test@test.com", password="test123")

        result = auth._build_document_request(
            doc_type="manual",
            model_id="809",
            sub_family_id=123,
            application_location_id=456,
            family_id=None
        )

        assert result == {
            "type": "manual",
            "params": {
                "model": "809",
                "subFamilyId": 123,
                "applicationLocationId": 456,
                "productType": "regular",
            },
            "productType": "regular",
            "subType": "REGULAR",
            "model": "809",
            "subFamilyId": 123,
            "applicationLocationId": 456,
        }

    def test_spec_sheet_request_with_family_id(self):
        """Should build specSheet request with familyId when provided."""
        auth = VibiaAuth(email="test@test.com", password="test123")

        result = auth._build_document_request(
            doc_type="specSheet",
            model_id="809",
            sub_family_id=123,
            application_location_id=456,
            family_id=789
        )

        assert result == {
            "type": "specSheet",
            "params": {
                "model": "809",
                "subFamilyId": 123,
                "applicationLocationId": 456,
                "productType": "regular",
                "familyId": 789,
            },
            "productType": "regular",
            "subType": "REGULAR",
            "model": "809",
            "subFamilyId": 123,
            "applicationLocationId": 456,
            "familyId": 789,
        }

    def test_images_request(self):
        """Should build images request correctly."""
        auth = VibiaAuth(email="test@test.com", password="test123")

        result = auth._build_document_request(
            doc_type="images",
            model_id="162",
            sub_family_id=999,
            application_location_id=111,
            family_id=222
        )

        assert result["type"] == "images"
        assert result["model"] == "162"
        assert result["params"]["model"] == "162"
        assert result["familyId"] == 222
        assert result["params"]["familyId"] == 222
        assert result["subType"] == "REGULAR"


class TestVibiaAuthInitialization:
    """Unit tests for VibiaAuth initialization."""

    def test_init_with_explicit_credentials(self):
        """Should initialize with explicitly provided credentials."""
        auth = VibiaAuth(
            email="user@example.com",
            password="secure_password",
            base_url="https://custom.vibia.com"
        )

        assert auth.email == "user@example.com"
        assert auth.password == "secure_password"
        assert auth.base_url == "https://custom.vibia.com"
        assert auth.client is None
        assert auth.auth_token is None

    def test_init_defaults_to_env_vars(self, monkeypatch):
        """Should fall back to environment variables when credentials not provided."""
        monkeypatch.setenv("VIBIA_EMAIL", "env@example.com")
        monkeypatch.setenv("VIBIA_PASSWORD", "env_password")

        auth = VibiaAuth()

        assert auth.email == "env@example.com"
        assert auth.password == "env_password"
        assert auth.base_url == "https://api.vibia.com"

    def test_init_without_credentials_or_env_vars(self, monkeypatch):
        """Should initialize with None credentials when neither provided nor in env."""
        monkeypatch.delenv("VIBIA_EMAIL", raising=False)
        monkeypatch.delenv("VIBIA_PASSWORD", raising=False)

        auth = VibiaAuth()

        assert auth.email is None
        assert auth.password is None

    def test_login_raises_without_credentials(self):
        """Should raise ValueError when attempting login without credentials."""
        auth = VibiaAuth(email=None, password=None)

        with pytest.raises(ValueError, match="Vibia credentials required"):
            auth.login()
