"""Unit tests for asset_downloader.py pure functions."""

from src.downloaders.asset_downloader import _generate_image_filename


class TestGenerateImageFilename:
    """Tests for _generate_image_filename function."""

    def test_product_image_index_0_returns_featured(self):
        """Should return 'featured.jpg' for first product image."""
        result = _generate_image_filename("product", 0, ".jpg")

        assert result == "featured.jpg"

    def test_product_image_index_1_returns_product_01(self):
        """Should return 'product_01.jpg' for second product image."""
        result = _generate_image_filename("product", 1, ".jpg")

        assert result == "product_01.jpg"

    def test_product_image_with_png_extension(self):
        """Should preserve file extension."""
        result = _generate_image_filename("product", 2, ".png")

        assert result == "product_02.png"

    def test_project_image_index_0(self):
        """Should return 'project_00.jpg' for first project image."""
        result = _generate_image_filename("project", 0, ".jpg")

        assert result == "project_00.jpg"

    def test_project_image_index_5(self):
        """Should return 'project_05.jpg' for sixth project image."""
        result = _generate_image_filename("project", 5, ".jpg")

        assert result == "project_05.jpg"

    def test_project_image_with_webp_extension(self):
        """Should preserve file extension for project images."""
        result = _generate_image_filename("project", 3, ".webp")

        assert result == "project_03.webp"

    def test_none_type_index_0_returns_featured(self):
        """Should return 'featured.jpg' when type is None and index is 0."""
        result = _generate_image_filename(None, 0, ".jpg")

        assert result == "featured.jpg"

    def test_none_type_index_1_returns_numbered(self):
        """Should return '01.jpg' when type is None and index > 0."""
        result = _generate_image_filename(None, 1, ".jpg")

        assert result == "01.jpg"

    def test_handles_double_digit_indices(self):
        """Should format indices with zero padding."""
        result = _generate_image_filename("product", 15, ".jpg")

        assert result == "product_15.jpg"

    def test_handles_large_indices(self):
        """Should handle large index numbers."""
        result = _generate_image_filename("project", 99, ".jpg")

        assert result == "project_99.jpg"

    def test_preserves_jpeg_extension(self):
        """Should handle .jpeg extension."""
        result = _generate_image_filename("product", 1, ".jpeg")

        assert result == "product_01.jpeg"

    def test_preserves_gif_extension(self):
        """Should handle .gif extension."""
        result = _generate_image_filename("project", 2, ".gif")

        assert result == "project_02.gif"
