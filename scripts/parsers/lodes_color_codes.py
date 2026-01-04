"""Extended Lodes color code mappings extracted from PDF analysis.

The 4-digit color codes follow this pattern:
- First 2 digits: Finish/Color code
- Last 2 digits: LED temperature or size variant

Examples:
- 1027 = Glossy White + 2700K
- 2030 = Glossy Black + 3000K
- 4527 = Matte Champagne + 2700K
"""

# Base finish/color codes (first 2 digits)
FINISH_CODES = {
    # Glossy finishes
    "10": {"en": "Glossy White", "de": "Bianco Lucido", "it": "Bianco Lucido"},
    "12": {"en": "Glossy White", "de": "Bianco Lucido", "it": "Bianco Lucido"},
    "20": {"en": "Glossy Black", "de": "Nero Lucido", "it": "Nero Lucido"},
    "22": {"en": "Glossy Black", "de": "Nero Lucido", "it": "Nero Lucido"},
    # Matte finishes (existing codes)
    "10": {"en": "Matte White", "de": "Weiß Matt", "it": "Bianco Opaco"},
    "20": {"en": "Matte Black", "de": "Schwarz Matt", "it": "Nero Opaco"},
    "35": {"en": "Coppery Bronze", "de": "Bronze", "it": "Bronzo Ramato"},
    "45": {"en": "Matte Champagne", "de": "Champagner Matt", "it": "Champagne Opaco"},
    # Metal finishes
    "40": {"en": "Chrome", "de": "Chrom", "it": "Cromo"},
    "46": {"en": "Glossy Bronze", "de": "Bronze Glänzend", "it": "Bronzo Lucido"},
    "47": {"en": "Brushed Chrome", "de": "Chrom Gebürstet", "it": "Cromo Spazzolato"},
    "50": {"en": "Gold", "de": "Gold", "it": "Oro"},
    "55": {"en": "Rose Gold", "de": "Roségold", "it": "Oro Rosa"},
    "60": {"en": "Lacquer Red", "de": "Lack Rot", "it": "Rosso Laccato"},
    "67": {
        "en": "Extra Matte Champagne",
        "de": "Extra Matt Champagner",
        "it": "Champagne Extra Opaco",
    },
    # Glass/diffuser codes
    "00": {"en": "Clear Glass", "de": "Klares Glas", "it": "Vetro Trasparente"},
    "01": {"en": "Frosted White", "de": "Weiß Satiniert", "it": "Bianco Satinato"},
    "13": {"en": "Frosted White", "de": "Weiß Satiniert", "it": "Bianco Satinato"},
    "43": {"en": "Glossy Smoke", "de": "Rauch Glänzend", "it": "Fumo Lucido"},
    "86": {"en": "White Silk", "de": "Weiß Seide", "it": "Bianco Seta"},
    # Additional found codes
    "02": {"en": "Clear", "de": "Transparent", "it": "Trasparente"},
    "03": {"en": "Frosted", "de": "Satiniert", "it": "Satinato"},
    "04": {"en": "Smoke", "de": "Rauch", "it": "Fumo"},
    "05": {"en": "Bronze", "de": "Bronze", "it": "Bronzo"},
    "06": {"en": "Red", "de": "Rot", "it": "Rosso"},
    "07": {"en": "Green", "de": "Grün", "it": "Verde"},
    "08": {"en": "Amber", "de": "Bernstein", "it": "Ambra"},
}

# LED temperature codes (last 2 digits)
LED_TEMP_CODES = {
    "27": {"temp": "2700K", "desc_en": "Warm White", "desc_de": "Warmweiß"},
    "30": {"temp": "3000K", "desc_en": "Warm White", "desc_de": "Warmweiß"},
    "35": {"temp": "3500K", "desc_en": "Neutral White", "desc_de": "Neutralweiß"},
    "40": {"temp": "4000K", "desc_en": "Cool White", "desc_de": "Kaltweiß"},
    # Size variants (when not LED temperature)
    "20": {"size": "Ø20cm", "desc_en": "20cm diameter", "desc_de": "20cm Durchmesser"},
    "25": {"size": "Ø25cm", "desc_en": "25cm diameter", "desc_de": "25cm Durchmesser"},
}


def parse_lodes_color_code(code: str) -> dict[str, str]:
    """Parse a 4-digit Lodes color code into finish and variant.

    Args:
        code: 4-digit code like "1027", "2030", "4527"

    Returns:
        Dictionary with color_name_en, color_name_de, and details
    """
    if len(code) != 4:
        return {
            "color_name_en": f"Color {code}",
            "color_name_de": f"Farbe {code}",
            "finish_code": code[:2] if len(code) >= 2 else code,
            "variant_code": code[2:] if len(code) >= 2 else "",
        }

    finish_code = code[:2]
    variant_code = code[2:]

    # Get finish/color info
    finish = FINISH_CODES.get(
        finish_code,
        {
            "en": f"Color {finish_code}",
            "de": f"Farbe {finish_code}",
        },
    )

    # Get variant info (LED temp or size)
    variant = LED_TEMP_CODES.get(variant_code, {})

    # Build descriptive name
    color_name_en = finish["en"]
    color_name_de = finish["de"]

    if "temp" in variant:
        color_name_en += f" - {variant['temp']}"
        color_name_de += f" - {variant['temp']}"
    elif "size" in variant:
        color_name_en += f" - {variant['desc_en']}"
        color_name_de += f" - {variant['desc_de']}"
    else:
        # Unknown variant code
        color_name_en += f" (variant {variant_code})"
        color_name_de += f" (Variante {variant_code})"

    return {
        "color_name_en": color_name_en,
        "color_name_de": color_name_de,
        "finish_code": finish_code,
        "variant_code": variant_code,
    }
