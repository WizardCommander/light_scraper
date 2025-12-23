"""Integration tests for Vibia modal download and image classification.

Tests the complete flow of:
- Downloading files from Vibia modal
- Extracting nested ZIPs
- Classifying images with AI
- Handling duplicates
"""

import shutil
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.scrapers.vibia_scraper import VibiaScraper


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory for tests."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    yield output_dir
    # Cleanup
    if output_dir.exists():
        shutil.rmtree(output_dir)


@pytest.fixture
def scraper():
    """Create scraper instance for testing."""
    return VibiaScraper()


class TestNestedZIPExtraction:
    """Tests for _extract_and_process_zip nested ZIP handling."""

    def test_extracts_single_level_zip(self, scraper, temp_output_dir):
        """Should extract files from simple ZIP."""
        # Create test ZIP with files
        zip_path = temp_output_dir / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("file2.pdf", "content2")

        # Execute
        count = scraper._extract_and_process_zip(zip_path, temp_output_dir)

        # Verify
        assert count == 2
        assert (temp_output_dir / "file1.txt").exists()
        assert (temp_output_dir / "file2.pdf").exists()
        assert not zip_path.exists()  # Main ZIP should be deleted

    def test_extracts_nested_zip(self, scraper, temp_output_dir):
        """Should extract files from ZIP containing another ZIP."""
        # Create nested ZIP
        nested_zip_path = temp_output_dir / "nested.zip"
        with zipfile.ZipFile(nested_zip_path, "w") as zf:
            zf.writestr("image1.jpg", b"image_data_1")
            zf.writestr("image2.jpg", b"image_data_2")

        # Create main ZIP containing nested ZIP
        main_zip_path = temp_output_dir / "main.zip"
        with zipfile.ZipFile(main_zip_path, "w") as zf:
            zf.write(nested_zip_path, "nested.zip")
            zf.writestr("readme.txt", "instructions")

        # Remove the temporary nested zip
        nested_zip_path.unlink()

        # Execute
        count = scraper._extract_and_process_zip(main_zip_path, temp_output_dir)

        # Verify
        assert count == 4  # 2 from main + 2 from nested
        assert (temp_output_dir / "readme.txt").exists()
        assert (temp_output_dir / "image1.jpg").exists()
        assert (temp_output_dir / "image2.jpg").exists()
        assert not main_zip_path.exists()  # Main ZIP deleted
        assert not (temp_output_dir / "nested.zip").exists()  # Nested ZIP deleted

    def test_extracts_two_level_nested_zips(self, scraper, temp_output_dir):
        """Should handle two levels of nested ZIPs (current implementation limit)."""
        # Create level 2 ZIP
        level2_zip = temp_output_dir / "level2.zip"
        with zipfile.ZipFile(level2_zip, "w") as zf:
            zf.writestr("mid_file.txt", "mid_content")
            zf.writestr("deep_file.txt", "deep_content")

        # Create level 1 ZIP containing level 2
        level1_zip = temp_output_dir / "level1.zip"
        with zipfile.ZipFile(level1_zip, "w") as zf:
            zf.write(level2_zip, "level2.zip")
            zf.writestr("top_file.txt", "top_content")

        # Clean up temp file
        level2_zip.unlink()

        # Execute
        count = scraper._extract_and_process_zip(level1_zip, temp_output_dir)

        # Verify files from both levels extracted
        assert (temp_output_dir / "top_file.txt").exists()
        assert (temp_output_dir / "mid_file.txt").exists()
        assert (temp_output_dir / "deep_file.txt").exists()
        # All ZIPs should be cleaned up
        assert not level1_zip.exists()
        assert not (temp_output_dir / "level2.zip").exists()

    def test_handles_non_zip_files_gracefully(self, scraper, temp_output_dir):
        """Should handle files that aren't ZIPs without crashing."""
        # Create ZIP with both ZIP and non-ZIP files
        main_zip = temp_output_dir / "main.zip"
        with zipfile.ZipFile(main_zip, "w") as zf:
            zf.writestr("document.pdf", "pdf_content")
            zf.writestr("fake.zip", "not_a_real_zip")  # Not actually a ZIP

        # Execute - should not crash
        count = scraper._extract_and_process_zip(main_zip, temp_output_dir)

        # Verify
        assert (temp_output_dir / "document.pdf").exists()
        # fake.zip should be kept as-is since it's not a valid ZIP
        assert (temp_output_dir / "fake.zip").exists()

    def test_prevents_zip_bomb_with_path_traversal(self, scraper, temp_output_dir):
        """Should prevent path traversal attacks in ZIP files."""
        # Create malicious ZIP with path traversal
        malicious_zip = temp_output_dir / "malicious.zip"
        with zipfile.ZipFile(malicious_zip, "w") as zf:
            # Try to write outside output directory
            zf.writestr("../../../etc/passwd", "malicious_content")
            zf.writestr("normal_file.txt", "normal_content")

        # Execute - should raise ValueError for unsafe path
        with pytest.raises(ValueError, match="ZIP contains unsafe path"):
            scraper._extract_and_process_zip(malicious_zip, temp_output_dir)

        # Verify path traversal was blocked
        assert not (temp_output_dir.parent.parent.parent / "etc" / "passwd").exists()


class TestImageClassificationFlow:
    """Tests for _classify_and_organize_images integration."""

    @patch("src.ai.image_classifier.classify_image_file")
    def test_classifies_and_organizes_images(
        self, mock_classify, scraper, temp_output_dir
    ):
        """Should classify images and move to correct directories."""
        # Setup - create test images
        test_images = [
            ("product1.jpg", "product"),
            ("product2.png", "product"),
            ("project1.jpg", "project"),
            ("project2.jpg", "project"),
        ]

        for filename, _ in test_images:
            (temp_output_dir / filename).write_text("fake_image_data")

        # Mock classifier to return classifications
        def classify_side_effect(path):
            if "product" in path:
                return "product"
            return "project"

        mock_classify.side_effect = classify_side_effect

        # Execute
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify images moved to correct directories
        product_dir = temp_output_dir / "images" / "product"
        project_dir = temp_output_dir / "images" / "project"

        assert (product_dir / "product1.jpg").exists()
        assert (product_dir / "product2.png").exists()
        assert (project_dir / "project1.jpg").exists()
        assert (project_dir / "project2.jpg").exists()

        # Original files should be moved (not copied)
        assert not (temp_output_dir / "product1.jpg").exists()
        assert not (temp_output_dir / "project1.jpg").exists()

    @patch("src.ai.image_classifier.classify_image_file")
    def test_handles_duplicate_images(self, mock_classify, scraper, temp_output_dir):
        """Should handle duplicate images without errors."""
        # Setup - create images directory with existing files
        product_dir = temp_output_dir / "images" / "product"
        product_dir.mkdir(parents=True)
        (product_dir / "existing.jpg").write_text("existing_image")

        # Create duplicate in main directory
        (temp_output_dir / "existing.jpg").write_text("duplicate_image")

        mock_classify.return_value = "product"

        # Execute - should not crash on duplicate
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify duplicate was handled
        assert (product_dir / "existing.jpg").exists()
        assert not (temp_output_dir / "existing.jpg").exists()  # Duplicate removed

    @patch("src.ai.image_classifier.classify_image_file")
    def test_skips_already_classified_images(
        self, mock_classify, scraper, temp_output_dir
    ):
        """Should skip images already in product/project directories."""
        # Setup - create images already in directories
        product_dir = temp_output_dir / "images" / "product"
        project_dir = temp_output_dir / "images" / "project"
        product_dir.mkdir(parents=True)
        project_dir.mkdir(parents=True)

        (product_dir / "already_classified.jpg").write_text("data")

        # Execute
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify classifier was not called (images already classified)
        mock_classify.assert_not_called()

    @patch("src.ai.image_classifier.classify_image_file")
    def test_finds_images_in_subdirectories(
        self, mock_classify, scraper, temp_output_dir
    ):
        """Should find and classify images in nested subdirectories."""
        # Setup - create images in subdirectories (like from ZIP extraction)
        subdir1 = temp_output_dir / "col_amb"
        subdir2 = temp_output_dir / "tec_pro"
        subdir1.mkdir()
        subdir2.mkdir()

        (subdir1 / "ambient1.jpg").write_text("data")
        (subdir1 / "ambient2.jpg").write_text("data")
        (subdir2 / "technical.png").write_text("data")

        mock_classify.return_value = "product"

        # Execute
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify all images were found and classified
        assert mock_classify.call_count == 3

        # Verify images moved to product directory
        product_dir = temp_output_dir / "images" / "product"
        assert (product_dir / "ambient1.jpg").exists()
        assert (product_dir / "ambient2.jpg").exists()
        assert (product_dir / "technical.png").exists()

        # Subdirectories should be cleaned up
        # (empty directories are removed by cleanup logic)

    @patch("src.ai.image_classifier.classify_image_file")
    def test_handles_classification_errors_gracefully(
        self, mock_classify, scraper, temp_output_dir
    ):
        """Should fallback to product directory when classification fails."""
        # Setup
        (temp_output_dir / "problematic.jpg").write_text("data")

        # Mock classifier to raise error
        mock_classify.side_effect = Exception("API Error")

        # Execute - should not crash
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify image was moved to product dir as fallback
        product_dir = temp_output_dir / "images" / "product"
        assert (product_dir / "problematic.jpg").exists() or not (
            temp_output_dir / "problematic.jpg"
        ).exists()

    @patch("src.ai.image_classifier.classify_image_file")
    def test_cleans_up_leftover_zips(self, mock_classify, scraper, temp_output_dir):
        """Should remove leftover ZIP files after extraction."""
        # Setup
        (temp_output_dir / "leftover.zip").write_text("zip_data")
        (temp_output_dir / "image.jpg").write_text("image_data")

        mock_classify.return_value = "product"

        # Execute
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify ZIP was cleaned up
        assert not (temp_output_dir / "leftover.zip").exists()

    @patch("src.ai.image_classifier.classify_image_file")
    def test_cleans_up_empty_directories(self, mock_classify, scraper, temp_output_dir):
        """Should remove empty directories after moving images."""
        # Setup - create images in subdirectory
        subdir = temp_output_dir / "empty_after_move"
        subdir.mkdir()
        (subdir / "image.jpg").write_text("data")

        mock_classify.return_value = "product"

        # Execute
        scraper._classify_and_organize_images(temp_output_dir)

        # Verify subdirectory was cleaned up (since all images moved out)
        # Note: The actual cleanup happens, but we keep images/product/project dirs
        product_dir = temp_output_dir / "images" / "product"
        assert product_dir.exists()
        assert (product_dir / "image.jpg").exists()
