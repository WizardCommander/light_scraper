"""Unit tests for output_base parameter functionality.

Following CLAUDE.md: parameterized inputs, test entire structure, strong assertions.
Tests verify that custom output directories are respected across scrapers and orchestrator.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.models import SKU, ProductData, Manufacturer
from src.scrapers.vibia_scraper import VibiaScraper
from src.scrapers.lodes_scraper import LodesScraper
from src.orchestrator import ScraperOrchestrator


@pytest.mark.unit
class TestVibiaScraperOutputBase:
    """Test Vibia scraper respects output_base parameter."""

    @patch("src.scrapers.vibia_scraper.VibiaScraper._ensure_browser")
    @patch("src.scrapers.vibia_scraper.VibiaScraper._extract_json_data")
    @patch("src.scrapers.vibia_scraper.VibiaScraper.download_product_files")
    def test_scrape_product_uses_custom_output_base(
        self, mock_download, mock_json, mock_browser
    ):
        """Should use custom output_base when downloading files."""
        # Setup mocks
        mock_json.return_value = {
            "props": {
                "pageProps": {
                    "featureProps": {
                        "data": {
                            "name": "Test Product",
                            "technicalInfo": {"description": []},
                            "hero": {"media": {}},
                        },
                        "collection": {},
                    }
                }
            }
        }

        scraper = VibiaScraper()
        scraper._page = Mock()
        scraper._page.goto = Mock()
        scraper._page.wait_for_load_state = Mock()

        custom_output = "custom/output/path"
        scraper.scrape_product(SKU("0162"), output_base=custom_output)

        # Verify download_product_files was called with correct output_dir
        assert mock_download.called
        call_args = mock_download.call_args
        output_dir = call_args[1]["output_dir"]
        # Normalize paths for cross-platform comparison
        output_dir_normalized = str(output_dir).replace("\\", "/")
        assert output_dir_normalized.startswith(custom_output)
        assert "0162" in output_dir_normalized

    @patch("src.scrapers.vibia_scraper.VibiaScraper._ensure_browser")
    @patch("src.scrapers.vibia_scraper.VibiaScraper._extract_json_data")
    @patch("src.scrapers.vibia_scraper.VibiaScraper.download_product_files")
    def test_scrape_product_uses_default_output_base(
        self, mock_download, mock_json, mock_browser
    ):
        """Should use default 'output' when output_base not provided."""
        # Setup mocks
        mock_json.return_value = {
            "props": {
                "pageProps": {
                    "featureProps": {
                        "data": {
                            "name": "Test Product",
                            "technicalInfo": {"description": []},
                            "hero": {"media": {}},
                        },
                        "collection": {},
                    }
                }
            }
        }

        scraper = VibiaScraper()
        scraper._page = Mock()
        scraper._page.goto = Mock()
        scraper._page.wait_for_load_state = Mock()

        scraper.scrape_product(SKU("0162"))

        # Verify download_product_files was called with default output
        assert mock_download.called
        call_args = mock_download.call_args
        output_dir = call_args[1]["output_dir"]
        assert str(output_dir).startswith("output")


@pytest.mark.unit
class TestLodesScraperOutputBase:
    """Test Lodes scraper accepts output_base parameter."""

    def test_scrape_product_accepts_output_base_signature(self):
        """Should accept output_base parameter in method signature."""
        import inspect

        scraper = LodesScraper()
        sig = inspect.signature(scraper.scrape_product)

        # Verify output_base parameter exists with default value
        assert "output_base" in sig.parameters
        assert sig.parameters["output_base"].default == "output"


@pytest.mark.unit
class TestOrchestratorOutputBase:
    """Test orchestrator passes output_base to scrapers."""

    @patch("src.orchestrator.get_scraper_class")
    @patch("src.orchestrator.export_to_woocommerce_csv")
    @patch("src.orchestrator.export_to_excel")
    def test_scrape_products_passes_output_dir_to_scraper(
        self, mock_excel, mock_csv, mock_get_scraper
    ):
        """Should pass output_dir as output_base to scraper.scrape_product()."""
        # Create mock scraper
        mock_scraper = Mock()
        mock_scraper.scrape_product = Mock(
            return_value=[
                ProductData(
                    sku=SKU("test-123"),
                    name="Test Product",
                    description="Test description",
                    manufacturer=Manufacturer("test"),
                    categories=["Test"],
                    attributes={},
                    images=[],
                )
            ]
        )
        mock_scraper.__enter__ = Mock(return_value=mock_scraper)
        mock_scraper.__exit__ = Mock(return_value=False)

        mock_scraper_class = Mock(return_value=mock_scraper)
        mock_get_scraper.return_value = mock_scraper_class

        # Mock exports
        mock_csv.return_value = Path("test.csv")
        mock_excel.return_value = Path("test.xlsx")

        orchestrator = ScraperOrchestrator()
        custom_output = "custom/output/directory"

        orchestrator.scrape_products(
            manufacturer="test",
            skus=["test-123"],
            output_dir=custom_output,
        )

        # Verify scraper.scrape_product was called with output_base=custom_output
        assert mock_scraper.scrape_product.called
        call_args = mock_scraper.scrape_product.call_args
        assert call_args[0][0] == SKU("test-123")
        assert call_args[1]["output_base"] == custom_output

    @patch("src.orchestrator.get_scraper_class")
    @patch("src.orchestrator.export_to_woocommerce_csv")
    @patch("src.orchestrator.export_to_excel")
    def test_scrape_products_uses_default_output_dir(
        self, mock_excel, mock_csv, mock_get_scraper
    ):
        """Should pass default 'output' when output_dir not specified."""
        # Create mock scraper
        mock_scraper = Mock()
        mock_scraper.scrape_product = Mock(
            return_value=[
                ProductData(
                    sku=SKU("test-123"),
                    name="Test Product",
                    description="Test description",
                    manufacturer=Manufacturer("test"),
                    categories=["Test"],
                    attributes={},
                    images=[],
                )
            ]
        )
        mock_scraper.__enter__ = Mock(return_value=mock_scraper)
        mock_scraper.__exit__ = Mock(return_value=False)

        mock_scraper_class = Mock(return_value=mock_scraper)
        mock_get_scraper.return_value = mock_scraper_class

        # Mock exports
        mock_csv.return_value = Path("test.csv")
        mock_excel.return_value = Path("test.xlsx")

        orchestrator = ScraperOrchestrator()

        orchestrator.scrape_products(
            manufacturer="test",
            skus=["test-123"],
        )

        # Verify scraper.scrape_product was called with default output_base
        assert mock_scraper.scrape_product.called
        call_args = mock_scraper.scrape_product.call_args
        assert call_args[1]["output_base"] == "output"


@pytest.mark.unit
class TestCaseInsensitiveImageDetection:
    """Test Vibia scraper handles uppercase image extensions."""

    def test_find_image_files_detects_uppercase_extensions(self, tmp_path):
        """Should find images with uppercase extensions (JPG, PNG, etc.)."""
        # Create test images with various case extensions
        (tmp_path / "image1.jpg").touch()
        (tmp_path / "image2.JPG").touch()
        (tmp_path / "image3.png").touch()
        (tmp_path / "image4.PNG").touch()
        (tmp_path / "image5.jpeg").touch()
        (tmp_path / "image6.JPEG").touch()

        scraper = VibiaScraper()
        found_images = scraper._find_image_files(tmp_path)

        # Deduplicate results (Windows filesystem is case-insensitive)
        unique_images = {img.resolve() for img in found_images}

        # Should find all 6 images regardless of case
        assert len(unique_images) == 6

        # Verify all images are present (case-insensitive check)
        image_names_lower = {img.name.lower() for img in unique_images}
        assert "image1.jpg" in image_names_lower
        assert "image2.jpg" in image_names_lower
        assert "image3.png" in image_names_lower
        assert "image4.png" in image_names_lower
        assert "image5.jpeg" in image_names_lower
        assert "image6.jpeg" in image_names_lower

    def test_find_image_files_works_recursively(self, tmp_path):
        """Should find images in subdirectories."""
        # Create nested structure
        subdir = tmp_path / "nested" / "deep"
        subdir.mkdir(parents=True)

        (tmp_path / "root.jpg").touch()
        (tmp_path / "nested" / "middle.PNG").touch()
        (subdir / "deep.JPEG").touch()

        scraper = VibiaScraper()
        found_images = scraper._find_image_files(tmp_path)

        # Deduplicate results (Windows filesystem is case-insensitive)
        unique_images = {img.resolve() for img in found_images}

        # Should find all 3 images in nested structure
        assert len(unique_images) == 3

        # Verify all images are present (case-insensitive check)
        image_names_lower = {img.name.lower() for img in unique_images}
        assert "root.jpg" in image_names_lower
        assert "middle.png" in image_names_lower
        assert "deep.jpeg" in image_names_lower
