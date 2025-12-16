"""Image classification module using Claude Vision API.

Classifies product images into:
- "product": White/neutral studio background with isolated product
- "project": Environment/lifestyle images showing product in context
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from loguru import logger
from openai import OpenAI

ImageType = Literal["product", "project"]

CACHE_DIR = Path("output/.ai_cache/image_classification")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Classification prompt template
CLASSIFICATION_PROMPT = """Analyze this product photograph and classify it as one of two types:

1. PRODUCT IMAGE: White or neutral studio background with product isolated/centered
   - Clean, professional product photography
   - Minimal or no environment/context
   - Focus is entirely on the product itself

2. PROJECT IMAGE: Environment/lifestyle/contextual image
   - Product shown in a room or setting
   - Lifestyle photography with décor/furniture
   - Architectural or interior design context
   - Product in actual use/installation

Respond with EXACTLY ONE WORD:
- "product" if it's a studio product shot with white/neutral background
- "project" if it shows environment/context/lifestyle

Your answer:"""


def _get_cache_key(image_url: str) -> str:
    """Generate cache key from image URL.

    Args:
        image_url: URL of the image

    Returns:
        MD5 hash of the URL
    """
    return hashlib.md5(image_url.encode()).hexdigest()


def _load_from_cache(cache_key: str) -> ImageType | None:
    """Load classification result from cache.

    Args:
        cache_key: Cache key (MD5 hash)

    Returns:
        Cached image type or None if not cached
    """
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                return data.get("image_type")
        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
            return None
    return None


def _save_to_cache(cache_key: str, image_type: ImageType, image_url: str) -> None:
    """Save classification result to cache.

    Args:
        cache_key: Cache key (MD5 hash)
        image_type: Classification result
        image_url: Original image URL
    """
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        with open(cache_file, "w") as f:
            json.dump(
                {
                    "image_url": image_url,
                    "image_type": image_type,
                },
                f,
                indent=2,
            )
    except Exception as e:
        logger.warning(f"Failed to save to cache: {e}")


def _call_vision_api(client: OpenAI, image_url: str) -> str:
    """Call GPT-4 Vision API to classify image (pure API logic).

    Args:
        client: Initialized OpenAI client
        image_url: URL of the image to classify

    Returns:
        Raw response text from the API

    Raises:
        Exception: If API call fails
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                    {
                        "type": "text",
                        "text": CLASSIFICATION_PROMPT,
                    },
                ],
            }
        ],
    )

    return response.choices[0].message.content.strip().lower()


def _parse_classification_response(response_text: str) -> ImageType:
    """Parse and validate API response (pure function).

    Args:
        response_text: Raw response from API

    Returns:
        Validated ImageType

    Examples:
        >>> _parse_classification_response("product")
        "product"
        >>> _parse_classification_response("PROJECT")
        "project"
        >>> _parse_classification_response("invalid")
        "project"
    """
    normalized = response_text.strip().lower()

    if normalized == "product":
        return "product"
    elif normalized == "project":
        return "project"
    else:
        logger.warning(
            f"Unexpected classification response: '{response_text}', defaulting to 'project'"
        )
        return "project"


def classify_image_url(
    image_url: str,
    api_key: str | None = None,
) -> ImageType:
    """Classify product image from URL using GPT-4 Vision API.

    Determines if image has white/neutral studio background (product image)
    or environment/lifestyle background (project image).

    Args:
        image_url: URL of the image to classify
        api_key: OpenAI API key (optional, reads from OPENAI_API_KEY environment)

    Returns:
        "product" if white/studio background, "project" if environment/lifestyle

    Raises:
        Exception: If API call fails

    Examples:
        >>> classify_image_url("https://www.lodes.com/.../kelly.jpg")
        "product"
    """
    # Check cache first
    cache_key = _get_cache_key(image_url)
    cached_result = _load_from_cache(cache_key)
    if cached_result:
        logger.debug(f"Using cached classification for {image_url}: {cached_result}")
        return cached_result

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        # Call API and parse response
        response_text = _call_vision_api(client, image_url)
        image_type = _parse_classification_response(response_text)

        # Cache the result
        _save_to_cache(cache_key, image_type, image_url)

        logger.info(f"Classified image as '{image_type}': {image_url}")
        return image_type

    except Exception as e:
        logger.error(f"Image classification failed for {image_url}: {e}")
        # Default to "project" on error (more conservative)
        return "project"
