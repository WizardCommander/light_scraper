"""Vibia authentication module for accessing protected resources.

Handles login and session management for downloading datasheets and manuals.
"""

import os
import time
import json
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
            # Define headers to mimic a real browser, based on user-provided cURL
            browser_headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "origin": "https://vibia.com",
                "referer": "https://vibia.com/",
                "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"Android"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
            }

            # Initialize HTTP client with headers, cookie support, and extended timeout
            self.client = httpx.Client(
                headers=browser_headers,
                follow_redirects=True,
                http2=True,  # Enable HTTP/2
                timeout=httpx.Timeout(300.0, connect=10.0)
            )

            # Authenticate with Vibia API
            response = self.client.post(
                f"{self.base_url}/users/v1/auth/authenticate",
                json={"email": self.email, "password": self.password},
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

        # Build full request
        request = {
            "type": doc_type,
            "params": params,
            "productType": "regular",
            "subType": "REGULAR",
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

        This now includes a polling mechanism to handle async document generation.
        """
        if not self.client or not self.auth_token:
            logger.error("Not authenticated. Call login() first.")
            return None

        if document_types is None:
            document_types = ["manual"]

        try:
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
                f"Requesting {len(document_types)} document(s) for catalog {catalog_id}"
            )

            # Initial request to start document generation
            response = self.client.post(
                f"{self.base_url}/v2/documents/docs-web/global-generate",
                params={"catalogId": catalog_id, "lang": lang},
                json=payload,
            )

            logger.debug(f"Initial download request status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Failed to start document generation: {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return None

            # The response is now expected to be JSON with a URL for polling/downloading
            try:
                data = response.json()
                # The response is a list containing a dictionary
                if isinstance(data, list) and data:
                    download_url = data[0].get("url")
                else:
                    download_url = None

                if not download_url:
                    logger.error("API response did not contain a download URL.")
                    logger.debug(f"Response JSON: {data}")
                    return None

                # Poll the download URL until the file is ready
                max_retries = 15
                retry_delay = 20  # seconds

                for attempt in range(max_retries):
                    logger.info(f"Downloading from {download_url} (attempt {attempt + 1}/{max_retries})...")
                    try:
                        file_response = self.client.get(download_url, follow_redirects=True)

                        if file_response.status_code == 200 and "zip" in file_response.headers.get("content-type", ""):
                            logger.success(f"Successfully downloaded ZIP file ({len(file_response.content)} bytes).")
                            return file_response.content
                        
                        logger.warning(f"Download attempt {attempt + 1} failed with status {file_response.status_code}. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)

                    except httpx.ReadTimeout:
                        logger.warning(f"Read timeout on attempt {attempt + 1}. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)

                logger.error("Max retries reached. Failed to download file.")
                return None

            except json.JSONDecodeError:
                logger.error("Failed to decode JSON response from Vibia API.")
                # If it's not JSON, it might be the file directly (old behavior)
                if "zip" in response.headers.get("content-type", ""):
                    logger.info("Response seems to be a ZIP file directly. Processing.")
                    return response.content
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
