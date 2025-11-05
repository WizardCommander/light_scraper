# Product Scraper for Manufacturer Websites

Modular Python-based web scraper for extracting product data from lighting manufacturer websites and exporting to WooCommerce-compatible formats.

## Features

- 🎯 **Manufacturer-specific scrapers** - Modular architecture for easy expansion
- 📊 **Dual export formats** - WooCommerce CSV + Excel XLSX
- 🖼️ **Image management** - Automatic download and organization
- 🔄 **Retry logic** - Exponential backoff for reliability
- 🧪 **Type-safe** - Full Python type hints with branded types
- ✅ **Test coverage** - Unit and integration tests

## Supported Manufacturers

- **Lodes** (lodes.com) - Fully implemented

## Quick Start

### 1. Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Basic Usage

```bash
# Scrape specific products from Lodes
python -m src.cli --manufacturer lodes --skus kelly,megaphone,a-tube-suspension

# Read SKUs from a file (one per line)
python -m src.cli --manufacturer lodes --skus-file lodes_skus.txt

# Skip image downloads (faster for testing)
python -m src.cli --manufacturer lodes --skus kelly --no-images

# Custom output directory
python -m src.cli --manufacturer lodes --skus kelly --output my_output

# Enable verbose logging
python -m src.cli --manufacturer lodes --skus kelly -v
```

### 3. Output

The scraper generates:

```
output/
├── products.csv          # WooCommerce import-ready CSV
├── products.xlsx         # Excel master data file
└── images/
    └── lodes/
        ├── kelly/
        │   ├── featured.jpg
        │   ├── 01.jpg
        │   └── 02.jpg
        └── megaphone/
            └── featured.jpg
```

## Project Structure

```
product-scraper/
├── src/
│   ├── types.py                  # Branded type definitions
│   ├── scrapers/
│   │   ├── base_scraper.py      # Abstract base class
│   │   └── lodes_scraper.py     # Lodes implementation
│   ├── exporters/
│   │   ├── woocommerce_csv.py   # CSV exporter
│   │   └── excel_exporter.py    # Excel exporter
│   ├── downloaders/
│   │   └── asset_downloader.py  # Image/PDF downloader
│   ├── utils/
│   │   └── retry_handler.py     # Retry logic
│   ├── orchestrator.py           # Main controller
│   └── cli.py                    # Command-line interface
├── tests/
│   └── unit/                     # Unit tests
├── config/                       # Configuration files
└── output/                       # Generated files
```

## Adding a New Manufacturer

To add support for a new manufacturer website:

### Step 1: Research Site Structure

1. Analyze the target website's HTML structure
2. Document CSS selectors for key elements:
   - Product title
   - Description
   - Images
   - Technical specs
   - Categories
3. Create a `{manufacturer}_structure.md` file documenting your findings

### Step 2: Create Scraper Class

Create `src/scrapers/{manufacturer}_scraper.py`:

```python
from src.scrapers.base_scraper import BaseScraper
from src.types import SKU, ProductData, ScraperConfig, Manufacturer

class MyManufacturerScraper(BaseScraper):
    def __init__(self):
        config = ScraperConfig(
            manufacturer=Manufacturer("my-manufacturer"),
            base_url="https://www.example.com",
            rate_limit_delay=1.0,
        )
        super().__init__(config)

    def build_product_url(self, sku: SKU) -> str:
        return f"{self.config.base_url}/products/{sku}/"

    def scrape_product(self, sku: SKU) -> ProductData:
        if self._page is None:
            self.setup_browser()

        url = self.build_product_url(sku)
        self._page.goto(url, wait_until="networkidle")

        # Extract data using Playwright selectors
        name = self._extract_name(self._page)
        description = self._extract_description(self._page)
        images = self._extract_images(self._page)
        # ... etc

        return ProductData(
            sku=sku,
            name=name,
            description=description,
            manufacturer=self.config.manufacturer,
            categories=categories,
            attributes=attributes,
            images=images,
        )

    def _extract_name(self, page):
        # Your extraction logic here
        pass
```

### Step 3: Register Scraper

Add to `src/orchestrator.py`:

```python
from src.scrapers.my_manufacturer_scraper import MyManufacturerScraper

class ScraperOrchestrator:
    def __init__(self):
        self.scrapers = {
            "lodes": LodesScraper,
            "my-manufacturer": MyManufacturerScraper,  # Add here
        }
```

### Step 4: Update CLI

Add to choices in `src/cli.py`:

```python
parser.add_argument(
    "--manufacturer",
    "-m",
    required=True,
    choices=["lodes", "my-manufacturer"],  # Add here
    help="Manufacturer to scrape from",
)
```

### Step 5: Write Tests

Create `tests/unit/test_{manufacturer}_scraper.py` with unit tests for your extraction logic.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run with coverage
pytest --cov=src
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Both together
black src/ tests/ && mypy src/
```

### Logging

Logs are automatically saved to `logs/scraper_YYYY-MM-DD.log` with rotation.

## Configuration

Copy `.env.example` to `.env` and customize:

```env
RATE_LIMIT_DELAY=1.0
HEADLESS_BROWSER=true
OUTPUT_DIR=output
LOG_LEVEL=INFO
```

## WooCommerce Import

1. Export products using the scraper
2. In WooCommerce admin, go to **Products → Import**
3. Upload the generated `products.csv` file
4. Map columns (should auto-detect)
5. Run import

**Note**: Images must be publicly accessible URLs or manually uploaded to WordPress Media Library first.

## Troubleshooting

### Browser fails to launch
```bash
playwright install chromium
```

### Import errors in tests
```bash
pip install -e .
```

### Rate limiting / timeouts
Increase `rate_limit_delay` in scraper config or use `--verbose` flag to debug.

## Technical Details

- **Python**: 3.11+
- **Browser Automation**: Playwright
- **Data Processing**: pandas, openpyxl
- **Testing**: pytest
- **Logging**: loguru
- **Type Checking**: mypy

## License

Proprietary - Internal use only

## Support

For issues or questions, contact the development team.

---

**Milestone 1 Status**: ✅ Lodes.com scraper complete with CSV/XLSX export and image downloading
