"""Vibia authentication module for accessing protected resources.

Handles login and session management for downloading datasheets and manuals.
"""

import os
from typing import Optional

import httpx
from loguru import logger


class VibiaAuth:
    """Manages authentication with Vibia API."""

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        base_url: str = "https://api.vibia.com",
    ):
        """Initialize Vibia authentication.

        Args:
            email: Vibia account email (uses VIBIA_EMAIL env var if not provided)
            password: Vibia account password (uses VIBIA_PASSWORD env var if not provided)
            base_url: Base URL for Vibia API
        """
        self.email = email or os.getenv("VIBIA_EMAIL")
        self.password = password or os.getenv("VIBIA_PASSWORD")
        self.base_url = base_url
        self.client: Optional[httpx.Client] = None
        self.auth_token: Optional[str] = None

    def login(self) -> bool:
        """Authenticate with Vibia and obtain session/token.

        Returns:
            True if login successful, False otherwise

        Raises:
            ValueError: If credentials not provided
        """
        if not self.email or not self.password:
            raise ValueError(
                "Vibia credentials required. Set VIBIA_EMAIL and VIBIA_PASSWORD "
                "environment variables or pass to constructor."
            )

        logger.info(f"Logging in to Vibia as {self.email}")

        try:
            # Initialize HTTP client with cookie support
            self.client = httpx.Client(follow_redirects=True)

            # Authenticate with Vibia API
            response = self.client.post(
                f"{self.base_url}/users/v1/auth/authenticate",
                json={"email": self.email, "password": self.password},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                # Extract tokens from response
                data = response.json()
                self.auth_token = data.get("jwtToken")
                refresh_token = data.get("refreshToken")

                if self.auth_token:
                    # Store tokens as cookies for subsequent requests
                    self.client.cookies.set("vibia_jwt", self.auth_token)
                    if refresh_token:
                        self.client.cookies.set("vibia_refresh", refresh_token)

                    logger.success("Successfully authenticated with Vibia")
                    return True
                else:
                    logger.error("No JWT token in response")
                    return False
            else:
                logger.error(
                    f"Vibia login failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Vibia authentication error: {e}")
            return False

    def _build_document_request(
        self,
        doc_type: str,
        model_id: str,
        sub_family_id: int,
        application_location_id: int,
        family_id: Optional[int] = None,
    ) -> dict:
        """Build a single document request object for Vibia API.

        Note: The Vibia API requires fields to be present both in 'params' and at root level.
        This is not a bug - it's the actual API requirement.

        Args:
            doc_type: Document type (e.g., "manual", "specSheet", "images")
            model_id: Model ID
            sub_family_id: Product sub-family ID
            application_location_id: Application location ID
            family_id: Product family ID (optional)

        Returns:
            Document request dictionary
        """
        # Build base params
        params = {
            "model": model_id,
            "subFamilyId": sub_family_id,
            "applicationLocationId": application_location_id,
            "productType": "regular",
        }

        # Add familyId if provided
        if family_id:
            params["familyId"] = family_id

        # Build full request (API requires fields in both params and root)
        request = {
            "type": doc_type,
            "params": params,
            "productType": "regular",
            "subType": "REGULAR",
            **params,  # Spread params into root level
        }

        return request

    def download_documents(
        self,
        catalog_id: str,
        model_id: str,
        sub_family_id: int,
        application_location_id: int,
        family_id: Optional[int] = None,
        document_types: list[str] = None,
        lang: str = "en",
    ) -> Optional[bytes]:
        """Download documents from Vibia using authenticated session.

        Args:
            catalog_id: Product catalog ID (e.g., "809")
            model_id: Model ID (usually same as catalog_id)
            sub_family_id: Product sub-family ID
            application_location_id: Application location ID
            family_id: Product family ID (optional)
            document_types: List of document types to download
                (e.g., ["manual", "specSheet", "images"])
                If None, downloads manual by default
            lang: Language code (default: "en")

        Returns:
            Downloaded ZIP file bytes, or None if failed
        """
        if not self.client or not self.auth_token:
            logger.error("Not authenticated. Call login() first.")
            return None

        if document_types is None:
            document_types = ["manual"]

        try:
            # Build payload array - one request per document type
            payload = [
                self._build_document_request(
                    doc_type=doc_type,
                    model_id=model_id,
                    sub_family_id=sub_family_id,
                    application_location_id=application_location_id,
                    family_id=family_id,
                )
                for doc_type in document_types
            ]

            logger.info(
                f"Downloading {len(document_types)} document(s) for catalog {catalog_id}"
            )

            # Make download request
            response = self.client.post(
                f"{self.base_url}/v2/documents/docs-web/global-generate",
                params={"catalogId": catalog_id, "lang": lang},
                json=payload,
            )

            if response.status_code == 200:
                # Check if response is actually a ZIP file
                content_type = response.headers.get("content-type", "")
                if "zip" in content_type or len(response.content) > 0:
                    logger.success(
                        f"Successfully downloaded documents ({len(response.content)} bytes)"
                    )
                    return response.content
                else:
                    logger.warning(
                        f"Unexpected response format: {content_type}"
                    )
                    return None
            else:
                logger.error(
                    f"Document download failed: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

    def logout(self):
        """Close session and cleanup."""
        if self.client:
            self.client.close()
            self.client = None
        self.auth_token = None
        logger.info("Logged out from Vibia")
