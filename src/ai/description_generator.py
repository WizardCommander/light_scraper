"""AI-powered product description generator.

Following CLAUDE.md: pure functions with clear separation of concerns.
"""

import json
import os
from pathlib import Path
from typing import Optional

import anthropic
import httpx
from loguru import logger

from src.models import ProductData


def generate_description(
    product: ProductData,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    cache_dir: str = "output/.ai_cache",
) -> str:
    """Generate unique product description using Claude AI.

    Args:
        product: Product data to generate description for
        api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        model: Anthropic model to use (default: claude-sonnet-4-20250514)
        cache_dir: Directory to cache AI responses

    Returns:
        Generated description text

    Raises:
        ValueError: If API key not provided and not in environment
        Exception: If AI generation fails
    """
    # Get API key from parameter or environment
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError(
            "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
            "or pass api_key parameter."
        )

    # Check cache first
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    cache_file = cache_path / f"{product.sku}_description.json"
    if cache_file.exists():
        logger.info(f"Using cached description for {product.sku}")
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            return cache_data["description"]

    # Generate new description
    logger.info(f"Generating AI description for {product.name}")

    try:
        # Initialize client without httpx proxy detection
        http_client = httpx.Client()
        client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

        prompt = _build_prompt(product)

        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        description = message.content[0].text.strip()

        # Cache the result
        cache_data = {
            "sku": product.sku,
            "name": product.name,
            "description": description,
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Successfully generated description for {product.name}")
        return description

    except Exception as e:
        logger.error(f"Failed to generate description for {product.sku}: {e}")
        # Fallback to original description
        logger.warning("Using original description as fallback")
        return product.description


def _build_prompt(product: ProductData) -> str:
    """Build prompt for AI description generation.

    Args:
        product: Product data

    Returns:
        Formatted prompt string
    """
    # Format attributes for prompt
    specs = "\n".join(f"- {key}: {value}" for key, value in product.attributes.items())

    prompt = f"""You are a professional e-commerce copywriter for a luxury lighting retailer.

Product Name: {product.name}
Manufacturer: {product.manufacturer}
Categories: {", ".join(product.categories)}

Original Description:
{product.description}

Technical Specifications:
{specs if specs else "No specifications available"}

Write a unique, compelling product description (2-3 paragraphs) that:
1. Highlights the design aesthetics and unique features
2. Naturally mentions key technical specifications where relevant
3. Uses an elegant, sophisticated tone appropriate for luxury lighting
4. Is SEO-friendly with relevant keywords
5. Does NOT copy or closely paraphrase the original description
6. Focuses on benefits and use cases

Return ONLY the description text, no preamble or extra formatting."""

    return prompt


def generate_short_description(
    product: ProductData,
    max_words: int = 20,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    cache_dir: str = "output/.ai_cache",
) -> str:
    """Generate concise short description for product (max 20 words).

    Args:
        product: Product data to generate short description for
        max_words: Maximum number of words (default: 20)
        api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        model: Anthropic model to use (default: claude-sonnet-4-20250514)
        cache_dir: Directory to cache AI responses

    Returns:
        Short description text (≤max_words)

    Raises:
        ValueError: If API key not provided and not in environment
        Exception: If AI generation fails
    """
    # Get API key from parameter or environment
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError(
            "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
            "or pass api_key parameter."
        )

    # Check cache first
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    cache_file = cache_path / f"{product.sku}_short_description.json"
    if cache_file.exists():
        logger.info(f"Using cached short description for {product.sku}")
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            return cache_data["short_description"]

    # Generate new short description
    logger.info(f"Generating AI short description for {product.name}")

    try:
        # Initialize client without httpx proxy detection
        http_client = httpx.Client()
        client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

        prompt = _build_short_description_prompt(product, max_words)

        message = client.messages.create(
            model=model,
            max_tokens=256,
            temperature=0.3,  # Lower temperature for consistency
            messages=[{"role": "user", "content": prompt}],
        )

        short_desc = message.content[0].text.strip()

        # Cache the result
        cache_data = {
            "sku": product.sku,
            "name": product.name,
            "short_description": short_desc,
            "word_count": len(short_desc.split()),
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Successfully generated short description for {product.name} ({len(short_desc.split())} words)"
        )
        return short_desc

    except Exception as e:
        logger.error(f"Failed to generate short description for {product.sku}: {e}")
        # Fallback to truncated description
        logger.warning("Using truncated description as fallback")
        words = product.description.split()[:max_words]
        return " ".join(words) + (
            "..." if len(product.description.split()) > max_words else ""
        )


def _build_short_description_prompt(product: ProductData, max_words: int) -> str:
    """Build prompt for AI short description generation.

    Args:
        product: Product data
        max_words: Maximum word count

    Returns:
        Formatted prompt string
    """
    language = "German" if product.translated_to_german else "English"

    prompt = f"""You are a professional e-commerce copywriter creating a short product description for a catalog listing.

Product Name: {product.name}
Manufacturer: {product.manufacturer}

Original Description:
{product.description[:300]}...

Write a concise, engaging product description in {language} with MAXIMUM {max_words} words.

Requirements:
1. Focus on the product's essence and key appeal
2. Mention 1-2 standout features
3. Use an elegant, sophisticated tone
4. Be compelling and catalog-ready
5. CRITICAL: Use MAXIMUM {max_words} words (not {max_words + 1}, not {max_words + 2}, exactly {max_words} or fewer)

Return ONLY the short description, no preamble or extra text."""

    return prompt
