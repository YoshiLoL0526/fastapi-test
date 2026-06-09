from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import cycle
from typing import Sequence


@dataclass(frozen=True)
class CategoryTheme:
    base_items: tuple[str, ...]
    prefixes: tuple[str, ...]
    suffixes: tuple[str, ...]
    materials: tuple[str, ...]
    features: tuple[str, ...]
    use_cases: tuple[str, ...]
    image_family: str
    price_range: tuple[float, float]


@dataclass(frozen=True)
class ProductBlueprint:
    name: str
    slug: str
    description: str
    price: Decimal
    image_url: str


CATEGORY_THEMES: dict[str, CategoryTheme] = {
    "electronics": CategoryTheme(
        base_items=("Headphones", "Keyboard", "Webcam", "Desk Lamp", "Portable SSD", "Monitor Arm"),
        prefixes=("Nova", "Pulse", "Apex", "Vector", "Quantum", "Nimbus"),
        suffixes=("Prime", "Flux", "Core", "Edge", "Series", "Mk II"),
        materials=("anodized aluminum", "carbon polymer", "soft-touch matte resin", "braided composite"),
        features=("low-latency connectivity", "adaptive power delivery", "silent thermals", "precision controls"),
        use_cases=("hybrid workstations", "daily carry", "creator desks", "long benchmark sessions"),
        image_family="electronics",
        price_range=(39.0, 189.0),
    ),
    "smartphones-accessories": CategoryTheme(
        base_items=("Phone Case", "Charging Pad", "Car Mount", "Screen Protector", "Wallet", "Cable"),
        prefixes=("Orbit", "Magna", "Swift", "Halo", "Atlas", "Drift"),
        suffixes=("Guard", "Link", "Grip", "Flow", "Dock", "Lite"),
        materials=("impact foam", "tempered glass", "magnetic alloy", "woven nylon"),
        features=("drop resistance", "snap alignment", "tangle-free routing", "one-hand setup"),
        use_cases=("commuting", "travel kits", "fast charging setups", "everyday protection"),
        image_family="mobile",
        price_range=(8.0, 49.0),
    ),
    "clothing-fashion": CategoryTheme(
        base_items=("T-Shirt", "Rain Jacket", "Tote Bag", "Sunglasses", "Scarf", "Wallet"),
        prefixes=("Northwind", "Copperfield", "Ashen", "Mariner", "Solstice", "Harbor"),
        suffixes=("Cut", "Weave", "Fit", "Layer", "Edition", "Line"),
        materials=("organic cotton", "waxed canvas", "merino blend", "waterproof shell"),
        features=("seasonal versatility", "tailored comfort", "weather resistance", "minimal bulk"),
        use_cases=("city commutes", "weekend trips", "layered outfits", "daily wear"),
        image_family="fashion",
        price_range=(18.0, 110.0),
    ),
    "mens-clothing": CategoryTheme(
        base_items=("Oxford Shirt", "Jogger Pants", "Pullover", "Cargo Shorts", "Jeans", "Linen Shirt"),
        prefixes=("Foundry", "Ridge", "Slate", "Harbor", "Westline", "Summit"),
        suffixes=("Tailored", "Drift", "Field", "Transit", "Woven", "Classic"),
        materials=("stretch twill", "brushed cotton", "linen blend", "performance fleece"),
        features=("mobility", "breathable structure", "all-day comfort", "clean drape"),
        use_cases=("office days", "travel wardrobes", "warm climates", "transitional weather"),
        image_family="menswear",
        price_range=(28.0, 95.0),
    ),
    "home-garden": CategoryTheme(
        base_items=("Planter Set", "Storage Basket", "Diffuser", "String Lights", "Candle Set", "Bottle"),
        prefixes=("Willow", "Hearth", "Moss", "Amber", "Meadow", "Cedar"),
        suffixes=("Nest", "Bloom", "Haven", "Glow", "Craft", "Reserve"),
        materials=("ceramic glaze", "woven wicker", "double-wall steel", "natural wax"),
        features=("quiet ambiance", "compact storage", "easy cleaning", "warm lighting"),
        use_cases=("small apartments", "cozy corners", "gift bundles", "home refreshes"),
        image_family="home",
        price_range=(14.0, 75.0),
    ),
    "kitchen-dining": CategoryTheme(
        base_items=("Skillet", "Spatula Set", "French Press", "Kitchen Scale", "Mixing Bowl Set", "Mandoline"),
        prefixes=("Forge", "Harvest", "Brass", "Ember", "Stoneware", "Kitchen Guild"),
        suffixes=("Chef", "Prep", "Table", "Brew", "Slice", "Service"),
        materials=("cast iron", "food-grade silicone", "borosilicate glass", "brushed steel"),
        features=("heat retention", "quick prep", "easy pouring", "countertop precision"),
        use_cases=("meal prep", "weeknight cooking", "coffee rituals", "batch baking"),
        image_family="kitchen",
        price_range=(16.0, 88.0),
    ),
    "sports-outdoors": CategoryTheme(
        base_items=("Backpack", "Trekking Poles", "Hydration Belt", "Camping Hammock", "Headlamp", "Dry Bag"),
        prefixes=("Trailborn", "Granite", "Summit", "Wildpath", "Stormline", "Ranger"),
        suffixes=("Expedition", "Scout", "Traverse", "Camp", "Peak", "Rapid"),
        materials=("ripstop nylon", "aircraft aluminum", "weatherproof shell", "quick-dry mesh"),
        features=("load balance", "weather sealing", "night visibility", "packable storage"),
        use_cases=("weekend hikes", "long treks", "camp setups", "trail running"),
        image_family="outdoors",
        price_range=(18.0, 145.0),
    ),
    "fitness-exercise": CategoryTheme(
        base_items=("Resistance Bands", "Dumbbell", "Yoga Mat", "Pull-Up Bar", "Jump Rope", "Massage Gun"),
        prefixes=("Forgefit", "Pulse", "Titan", "Coreline", "Velocity", "Atlas"),
        suffixes=("Strength", "Motion", "Recovery", "Circuit", "Flex", "Endure"),
        materials=("reinforced latex", "powder-coated steel", "high-density foam", "impact ABS"),
        features=("progressive overload", "joint-friendly grip", "compact storage", "quiet operation"),
        use_cases=("home gyms", "warm-up circuits", "recovery days", "travel workouts"),
        image_family="fitness",
        price_range=(15.0, 140.0),
    ),
    "books-media": CategoryTheme(
        base_items=("Testing Handbook", "Python Guide", "Design Manual", "System Design Guide", "DevOps Handbook", "Refactoring Playbook"),
        prefixes=("Pragmatic", "Modern", "Applied", "Deep", "Field", "Mastery"),
        suffixes=("Companion", "Blueprint", "Atlas", "Notes", "Edition", "Primer"),
        materials=("annotated examples", "battle-tested patterns", "practical case studies", "dense reference charts"),
        features=("fast lookup", "project-based learning", "production realism", "incremental mastery"),
        use_cases=("team onboarding", "architecture reviews", "interview prep", "late-night debugging"),
        image_family="books",
        price_range=(22.0, 72.0),
    ),
    "fiction-literature": CategoryTheme(
        base_items=("Starfall Chronicle", "Desert Empire", "Orbital Rescue", "Wandering Archive", "Iron Kingdom", "Silent Horizon"),
        prefixes=("The", "A", "Chronicles of", "Legends of", "Songs of", "Tales of"),
        suffixes=("Awakening", "Rebellion", "Voyage", "Prophecy", "Labyrinth", "Final Dawn"),
        materials=("rich worldbuilding", "character-driven tension", "slow-burn mystery", "cinematic pacing"),
        features=("immersive atmosphere", "memorable dialogue", "sharp escalation", "high reread value"),
        use_cases=("weekend reading", "book clubs", "gift picks", "late-night page turns"),
        image_family="fiction",
        price_range=(12.0, 28.0),
    ),
}


REVIEW_OPENERS = {
    5: ("Outstanding", "Excellent", "Fantastic", "Top-tier"),
    4: ("Very solid", "Good value", "Reliable", "Happy with it"),
    3: ("Decent", "Serviceable", "Mixed feelings", "Okay overall"),
    2: ("Below expectations", "Rough around the edges", "Disappointing", "Needs work"),
    1: ("Avoid", "Very poor", "Frustrating", "Not worth it"),
}

REVIEW_IMPRESSIONS = {
    5: ("feels better than expected", "has become an easy recommendation", "delivers on every promise", "looks and performs like a premium item"),
    4: ("works exactly how I need", "has a few minor compromises", "lands in the sweet spot for the price", "holds up well in daily use"),
    3: ("does the job but nothing more", "feels average in hand", "is usable with some caveats", "needs a bit more polish"),
    2: ("shows quality issues quickly", "does not justify the price", "left me wanting a sturdier version", "needs better finishing"),
    1: ("misses the mark entirely", "was a bad buy for my use case", "feels unreliable from day one", "should have been returned immediately"),
}

REVIEW_CLOSERS = {
    5: ("Would buy again.", "I would absolutely recommend it.", "One of the best purchases in this batch.", "It stands out in a crowded category."),
    4: ("I would still recommend it.", "Worth considering if the specs fit your setup.", "A dependable pick overall.", "I would buy it again on sale."),
    3: ("Acceptable, but not memorable.", "Fine if your expectations are realistic.", "Not bad, just not special.", "Good enough for light use."),
    2: ("I would skip this version.", "There are better options nearby.", "Hard to recommend in its current form.", "Only worth it with a major discount."),
    1: ("I would not recommend it.", "Save your money.", "This one should be avoided.", "It needs a complete rethink."),
}


def slugify(text: str) -> str:
    return (
        text.lower()
        .replace("&", "and")
        .replace("'", "")
        .replace(",", "")
        .replace("#", "")
        .replace("/", "-")
        .replace("  ", " ")
        .replace(" ", "-")
    )


def _pick(seq: Sequence[str], index: int) -> str:
    return seq[index % len(seq)]


def generate_product_blueprint(category_slug: str, serial: int) -> ProductBlueprint:
    theme = CATEGORY_THEMES[category_slug]

    base = _pick(theme.base_items, serial)
    prefix = _pick(theme.prefixes, serial // max(1, len(theme.base_items)))
    suffix = _pick(theme.suffixes, serial // max(1, len(theme.base_items) * len(theme.prefixes)))
    material = _pick(
        theme.materials,
        serial // max(1, len(theme.base_items) * len(theme.prefixes) * len(theme.suffixes)),
    )
    feature = _pick(theme.features, serial * 3 + 1)
    use_case = _pick(theme.use_cases, serial * 5 + 2)

    if serial % 3 == 0:
        name = f"{prefix} {base} {suffix}"
    elif serial % 3 == 1:
        name = f"{prefix} {base} of {suffix}"
    else:
        name = f"{base} {suffix} by {prefix}"

    min_price, max_price = theme.price_range
    span = max_price - min_price
    rarity_band = ((serial * 17) % 19) / 18
    price = Decimal(str(round(min_price + (span * rarity_band), 2)))

    description = (
        f"Synthetic catalog item built from the {base} base type with the {prefix} prefix "
        f"and {suffix} suffix. Uses {material} for {feature} and is tuned for {use_case}."
    )

    slug = f"{slugify(name)}-{serial + 1}"
    image_url = f"https://cdn.example.com/products/{theme.image_family}/{slug}.jpg"

    return ProductBlueprint(
        name=name,
        slug=slug,
        description=description,
        price=price,
        image_url=image_url,
    )


def generate_review_copy(product_name: str, rating: int, serial: int) -> tuple[str, str]:
    opener = _pick(REVIEW_OPENERS[rating], serial)
    impression = _pick(REVIEW_IMPRESSIONS[rating], serial * 2 + 1)
    closer = _pick(REVIEW_CLOSERS[rating], serial * 3 + 2)
    title = f"{opener}: {product_name}"
    body = f"{product_name} {impression}. {closer}"
    return title, body
