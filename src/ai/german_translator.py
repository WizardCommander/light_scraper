"""German translation module using Claude API.

Translates product content to German for WooCommerce German stores.
Uses caching and language detection to minimize API costs and improve performance.
"""

import hashlib
import json
from pathlib import Path
from typing import Literal

import httpx
from anthropic import Anthropic
from langdetect import detect, LangDetectException
from loguru import logger

from src.models import ProductData

CACHE_DIR = Path("output/.ai_cache/translations")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


FieldType = Literal[
    "product_name", "description", "short_description", "category", "attribute"
]


def _is_already_german(text: str, min_length: int = 20) -> bool:
    """Detect if text is already in German to skip unnecessary translations.

    Args:
        text: Text to check
        min_length: Minimum text length for reliable detection (default: 20 chars)

    Returns:
        True if text is already German, False otherwise
    """
    if not text or len(text.strip()) < min_length:
        # For very short text, can't reliably detect - translate to be safe
        return False

    try:
        detected_lang = detect(text)
        is_german = detected_lang == "de"
        if is_german:
            logger.debug("Text already in German, skipping translation")
        return is_german
    except LangDetectException:
        # If detection fails, assume not German (better to translate unnecessarily)
        logger.debug("Language detection failed, will translate")
        return False


def translate_to_german(
    text: str,
    field_type: FieldType = "description",
    context: str = "lighting product",
) -> str:
    """Translate text to German using Claude with industry-specific terminology.

    Uses language detection to skip translation if text is already German,
    reducing API costs.

    Args:
        text: Text to translate
        field_type: Type of field being translated
        context: Additional context about the product

    Returns:
        Translated German text

    Raises:
        Exception: If translation fails
    """
    if not text or not text.strip():
        return text

    # Check if already German (skip API call to save costs)
    if _is_already_german(text):
        logger.debug(f"Skipping translation for {field_type} - already German")
        return text

    # Check cache first
    cache_key = _get_cache_key(text, field_type)
    cached_translation = _load_from_cache(cache_key)
    if cached_translation:
        logger.debug(f"Using cached translation for {field_type}")
        return cached_translation

    # Build appropriate prompt based on field type
    prompt = _build_translation_prompt(text, field_type, context)

    try:
        # Initialize client without httpx proxy detection
        http_client = httpx.Client()
        client = Anthropic(http_client=http_client)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        translated_text = message.content[0].text.strip()

        # Cache the result
        _save_to_cache(cache_key, translated_text)

        logger.debug(f"Translated {field_type} to German")
        return translated_text

    except Exception as e:
        logger.error(f"Translation failed for {field_type}: {e}")
        logger.warning(f"Returning original text: {text[:50]}...")
        return text


def translate_product_data(product: ProductData) -> ProductData:
    """Translate all text fields of a product to German.

    Args:
        product: Product data to translate

    Returns:
        New ProductData instance with translated text fields
    """
    logger.info(f"Translating product {product.sku} to German")

    # Translate main fields
    translated_name = translate_to_german(
        product.name, field_type="product_name", context="lighting product name"
    )

    translated_description = translate_to_german(
        product.description, field_type="description", context="lighting product"
    )

    # Translate categories
    translated_categories = [
        translate_to_german(cat, field_type="category", context="product category")
        for cat in product.categories
    ]

    # Translate attribute values (keep keys in English for consistency)
    translated_attributes = {}
    if product.attributes:
        for key, value in product.attributes.items():
            if isinstance(value, str) and value:
                translated_attributes[key] = translate_to_german(
                    value, field_type="attribute", context=f"product attribute {key}"
                )
            else:
                translated_attributes[key] = value

    # Create new ProductData with translated fields
    return ProductData(
        sku=product.sku,
        name=translated_name,
        description=translated_description,
        manufacturer=product.manufacturer,
        categories=translated_categories,
        attributes=translated_attributes,
        images=product.images,
        product_type=product.product_type,
        parent_sku=product.parent_sku,
        variation_attributes=product.variation_attributes,
        regular_price=product.regular_price,
        sale_price=product.sale_price,
        stock=product.stock,
        ean=product.ean,
        weight=product.weight,
        dimensions=product.dimensions,
        installation_type=product.installation_type,
        material=product.material,
        ip_rating=product.ip_rating,
        light_specs=product.light_specs,
        datasheet_url=product.datasheet_url,
        cable_length=product.cable_length,
        available_colors=product.available_colors,
        installation_manual_url=product.installation_manual_url,
        product_notes=product.product_notes,
        scraped_language="de",
        translated_to_german=True,
        short_description=product.short_description,
        original_name=product.original_name,
    )


def _build_translation_prompt(text: str, field_type: FieldType, context: str) -> str:
    """Build appropriate translation prompt based on field type.

    Args:
        text: Text to translate
        field_type: Type of field
        context: Additional context

    Returns:
        Translation prompt
    """
    base_instructions = """You are a professional translator specializing in lighting products for German e-commerce.
Translate the following text to natural, professional German.

Important guidelines:
- Use proper lighting industry terminology (Pendelleuchte, not "hängende Lampe")
- Maintain technical specifications exactly as written (IP ratings, watts, lumens, Kelvin)
- Keep brand names unchanged
- Use formal tone appropriate for product descriptions
- Do not add explanations or notes, return only the translation"""

    if field_type == "product_name":
        prompt = f"""{base_instructions}

Translate this lighting product name to German:
{text}

Return only the German product name."""

    elif field_type == "description":
        prompt = f"""{base_instructions}

Translate this lighting product description to German:
{text}

Return only the German description."""

    elif field_type == "category":
        prompt = f"""{base_instructions}

Translate this product category to German:
{text}

Return only the German category name (e.g., "Suspension" -> "Pendelleuchten")."""

    elif field_type == "attribute":
        prompt = f"""{base_instructions}

Translate this product attribute value to German (context: {context}):
{text}

Return only the translated value."""

    else:  # short_description
        prompt = f"""{base_instructions}

Translate this short product description to German:
{text}

Return only the German short description."""

    return prompt


def _get_cache_key(text: str, field_type: FieldType) -> str:
    """Generate cache key from text and field type.

    Args:
        text: Text being translated
        field_type: Type of field

    Returns:
        Cache key hash
    """
    content = f"{field_type}:{text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_from_cache(cache_key: str) -> str | None:
    """Load translation from cache if available.

    Args:
        cache_key: Cache key hash

    Returns:
        Cached translation or None if not found
    """
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("translation")
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_key}: {e}")
    return None


def _save_to_cache(cache_key: str, translation: str) -> None:
    """Save translation to cache.

    Args:
        cache_key: Cache key hash
        translation: Translated text
    """
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"translation": translation}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save cache {cache_key}: {e}")
