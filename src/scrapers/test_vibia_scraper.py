"""Unit tests for Vibia scraper security functions.

Following CLAUDE.md: unit tests for pure logic functions.
"""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from src.scrapers.vibia_scraper import VibiaScraper


class TestExtractZipSafely:
    """Unit tests for _extract_zip_safely method (security validation)."""

    def test_extracts_safe_zip_successfully(self, tmp_path: Path):
        """Should extract a safe ZIP file without errors."""
        scraper = VibiaScraper()

        # Create a safe ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("manual.pdf", b"PDF content")
            zip_file.writestr("spec.pdf", b"Spec content")
            zip_file.writestr("subfolder/image.jpg", b"Image content")

        zip_buffer.seek(0)

        # Extract safely
        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            scraper._extract_zip_safely(zip_ref, tmp_path)

        # Verify files were extracted
        assert (tmp_path / "manual.pdf").exists()
        assert (tmp_path / "spec.pdf").exists()
        assert (tmp_path / "subfolder" / "image.jpg").exists()
        assert (tmp_path / "manual.pdf").read_bytes() == b"PDF content"

    def test_rejects_path_traversal_attack(self, tmp_path: Path):
        """Should reject ZIP with path traversal attempts (../../etc/passwd)."""
        scraper = VibiaScraper()

        # Create malicious ZIP with path traversal
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("../../etc/passwd", b"malicious")

        zip_buffer.seek(0)

        # Should raise ValueError
        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            with pytest.raises(ValueError, match="ZIP contains unsafe path"):
                scraper._extract_zip_safely(zip_ref, tmp_path)

        # Verify no files were extracted
        assert not (tmp_path / "../../etc/passwd").exists()

    def test_rejects_absolute_path_attack(self, tmp_path: Path):
        """Should reject ZIP with absolute paths."""
        scraper = VibiaScraper()

        # Create malicious ZIP with absolute path
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            if Path("/").exists():  # Unix-like system
                zip_file.writestr("/tmp/malicious.txt", b"malicious")
            else:  # Windows
                zip_file.writestr("C:/Windows/malicious.txt", b"malicious")

        zip_buffer.seek(0)

        # Should raise ValueError
        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            with pytest.raises(ValueError, match="ZIP contains unsafe path"):
                scraper._extract_zip_safely(zip_ref, tmp_path)

    def test_rejects_zip_bomb(self, tmp_path: Path):
        """Should reject ZIP that exceeds size limit (zip bomb protection)."""
        scraper = VibiaScraper()

        # Create a ZIP that exceeds 500MB limit
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as zip_file:
            # Add files that total > 500MB
            large_content = b"X" * (100 * 1024 * 1024)  # 100MB
            for i in range(6):  # 6 * 100MB = 600MB
                zip_file.writestr(f"large_file_{i}.bin", large_content)

        zip_buffer.seek(0)

        # Should raise ValueError
        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            with pytest.raises(ValueError, match="exceeds limit"):
                scraper._extract_zip_safely(zip_ref, tmp_path)

    def test_allows_files_up_to_size_limit(self, tmp_path: Path):
        """Should allow ZIP files up to the 500MB limit."""
        scraper = VibiaScraper()

        # Create a ZIP just under 500MB
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as zip_file:
            # 450MB total (under limit)
            large_content = b"X" * (90 * 1024 * 1024)  # 90MB
            for i in range(5):  # 5 * 90MB = 450MB
                zip_file.writestr(f"large_file_{i}.bin", large_content)

        zip_buffer.seek(0)

        # Should NOT raise error
        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            scraper._extract_zip_safely(zip_ref, tmp_path)

        # Verify files exist
        assert (tmp_path / "large_file_0.bin").exists()

    def test_handles_empty_zip(self, tmp_path: Path):
        """Should handle empty ZIP files gracefully."""
        scraper = VibiaScraper()

        # Create empty ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            pass  # Empty ZIP

        zip_buffer.seek(0)

        # Should not raise error
        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            scraper._extract_zip_safely(zip_ref, tmp_path)


class TestExtractDownloadIds:
    """Unit tests for _extract_download_ids method."""

    def test_extracts_all_ids_successfully(self):
        """Should extract all required IDs from featureProps."""
        scraper = VibiaScraper()

        feature_props = {
            "data": {
                "id": 809
            },
            "collection": {
                "family": {"id": 10},
                "subFamily": {"id": 20},
                "applicationsLocations": [
                    {"id": 30, "name": "Indoor"},
                    {"id": 31, "name": "Outdoor"}
                ]
            }
        }

        result = scraper._extract_download_ids(feature_props)

        assert result == {
            "catalog_id": "809",
            "model_id": "809",
            "family_id": 10,
            "sub_family_id": 20,
            "application_location_id": 30  # Should use first location
        }

    def test_returns_none_when_catalog_id_missing(self):
        """Should return None when catalog ID is not present."""
        scraper = VibiaScraper()

        feature_props = {
            "data": {},  # No 'id' field
            "collection": {
                "family": {"id": 10},
                "subFamily": {"id": 20},
                "applicationsLocations": [{"id": 30}]
            }
        }

        result = scraper._extract_download_ids(feature_props)

        assert result is None

    def test_returns_none_when_family_id_missing(self):
        """Should return None when family ID is not present."""
        scraper = VibiaScraper()

        feature_props = {
            "data": {"id": 809},
            "collection": {
                "family": {},  # No 'id' field
                "subFamily": {"id": 20},
                "applicationsLocations": [{"id": 30}]
            }
        }

        result = scraper._extract_download_ids(feature_props)

        assert result is None

    def test_returns_none_when_application_locations_empty(self):
        """Should return None when applicationsLocations array is empty."""
        scraper = VibiaScraper()

        feature_props = {
            "data": {"id": 809},
            "collection": {
                "family": {"id": 10},
                "subFamily": {"id": 20},
                "applicationsLocations": []  # Empty array
            }
        }

        result = scraper._extract_download_ids(feature_props)

        assert result is None

    def test_uses_first_application_location(self):
        """Should use the first application location when multiple exist."""
        scraper = VibiaScraper()

        feature_props = {
            "data": {"id": 809},
            "collection": {
                "family": {"id": 10},
                "subFamily": {"id": 20},
                "applicationsLocations": [
                    {"id": 100, "name": "First"},
                    {"id": 200, "name": "Second"},
                    {"id": 300, "name": "Third"}
                ]
            }
        }

        result = scraper._extract_download_ids(feature_props)

        assert result["application_location_id"] == 100
