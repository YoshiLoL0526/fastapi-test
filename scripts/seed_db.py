#!/usr/bin/env python3
"""Seed the e-commerce database with realistic benchmark data.

Idempotent: safe to run multiple times. If categories already exist the script
exits without inserting duplicates.

Usage (from project root):
    python scripts/seed_db.py
"""
import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all models so SQLAlchemy registers their metadata
import api.models.cart  # noqa: F401
import api.models.inventory  # noqa: F401
import api.models.order  # noqa: F401
import api.models.payment  # noqa: F401
import api.models.product  # noqa: F401
import api.models.review  # noqa: F401
import api.models.user  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import AsyncSessionLocal
from api.core.security import hash_password
from api.models.cart import Coupon
from api.models.inventory import Inventory, InventoryMovement
from api.models.order import Order, OrderItem
from api.models.payment import Payment
from api.models.product import Category, Product
from api.models.review import Review
from api.models.user import Address, User

# ── Configuration ──────────────────────────────────────────────────────────────

SEED_PASSWORD = "TestPassword123!"
NUM_POOL_USERS = 50
NUM_REGULAR_USERS = 950
NUM_ADMIN_USERS = 5
NUM_PRODUCTS = 500
NUM_ORDERS = 200
NUM_REVIEWS = 1000
NUM_COUPONS = 10

# ── Static data ────────────────────────────────────────────────────────────────

# (name, slug, description, [(child_name, child_slug, child_description), ...])
CATEGORY_TREE = [
    (
        "Electronics", "electronics", "Electronic devices and accessories",
        [("Smartphones & Accessories", "smartphones-accessories", "Phones, cases and chargers")],
    ),
    (
        "Clothing & Fashion", "clothing-fashion", "Apparel for all occasions",
        [("Men's Clothing", "mens-clothing", "Shirts, pants, jackets and more")],
    ),
    (
        "Home & Garden", "home-garden", "Everything for your home and garden",
        [("Kitchen & Dining", "kitchen-dining", "Cookware, utensils and kitchen gadgets")],
    ),
    (
        "Sports & Outdoors", "sports-outdoors", "Equipment for sports and outdoor activities",
        [("Fitness & Exercise", "fitness-exercise", "Gym equipment and fitness gear")],
    ),
    (
        "Books & Media", "books-media", "Books, music and digital media",
        [("Fiction & Literature", "fiction-literature", "Novels, short stories and literary works")],
    ),
]

# (name, description, price) templates per category slug
PRODUCT_TEMPLATES: dict[str, list[tuple[str, str, float]]] = {
    "electronics": [
        ("Wireless Bluetooth Headphones Pro", "Premium 30hr battery with ANC", 79.99),
        ("USB-C GaN Charger 65W", "Multi-device fast charging", 34.99),
        ("Mechanical Keyboard TKL RGB", "Cherry MX switches, compact layout", 129.99),
        ("4K Webcam with Ring Light", "Auto-focus, 60fps, built-in mic", 89.99),
        ("Smart LED Desk Lamp", "Adjustable color temp and brightness", 45.99),
        ("Portable SSD 1TB", "USB 3.2 Gen 2, 1050 MB/s read speed", 99.99),
        ("Noise-Cancelling Earbuds", "True wireless with 8hr playtime", 59.99),
        ("USB Hub 10-Port", "7x USB-A 3.0 + 3x USB-C", 42.99),
        ("Monitor Arm Dual", "Fully adjustable, holds up to 32-inch screens", 74.99),
        ("HDMI 2.1 Cable 3m", "8K@60Hz, 48Gbps bandwidth", 12.99),
    ],
    "smartphones-accessories": [
        ("Shockproof Phone Case", "Military-grade drop protection", 14.99),
        ("Tempered Glass Screen Protector", "9H hardness anti-fingerprint", 9.99),
        ("15W Wireless Charging Pad", "Qi compatible fast charger", 24.99),
        ("USB-C to 3.5mm Adapter", "Hi-fi audio DAC adapter", 7.99),
        ("Aluminum Phone Stand", "Adjustable angle desk stand", 19.99),
        ("MagSafe Wallet", "Attachable card holder for 3 cards", 29.99),
        ("Car Phone Mount", "Dashboard vent clip with 360° rotation", 16.99),
        ("Fast Charge Cable 2m", "Braided nylon USB-C to USB-C 100W", 11.99),
        ("Selfie Ring Light", "Clip-on with 3 color modes", 13.99),
        ("Waterproof Phone Pouch", "Universal dry bag for water sports", 8.99),
    ],
    "clothing-fashion": [
        ("Classic Cotton T-Shirt", "100% organic cotton, pre-shrunk", 19.99),
        ("Slim Fit Chinos", "Wrinkle-resistant stretch fabric", 49.99),
        ("Genuine Leather Belt", "Full-grain leather with brushed buckle", 34.99),
        ("Merino Wool Scarf", "Soft and warm for cold weather", 24.99),
        ("Canvas Tote Bag", "Heavyweight canvas with interior pockets", 22.99),
        ("Waterproof Rain Jacket", "Breathable shell with sealed seams", 89.99),
        ("Polarized Sunglasses", "UV400 protection in acetate frame", 54.99),
        ("Leather Card Wallet", "Slim minimalist 6-card holder", 27.99),
        ("Cotton Baseball Cap", "Structured 6-panel with curved brim", 18.99),
        ("Insulated Bomber Jacket", "Water-resistant with quilted lining", 99.99),
    ],
    "mens-clothing": [
        ("Oxford Button-Down Shirt", "Classic fit 100% cotton poplin", 44.99),
        ("Slim Jogger Pants", "Athletic-inspired comfort fit", 39.99),
        ("Quarter-Zip Pullover", "Moisture-wicking fleece", 54.99),
        ("6-Pocket Cargo Shorts", "Utility shorts in ripstop fabric", 34.99),
        ("Crew-Neck Merino Sweater", "Lightweight merino wool blend", 64.99),
        ("Slim Dress Trousers", "Stretch fabric for all-day comfort", 59.99),
        ("Flannel Plaid Shirt", "Soft brushed cotton in seasonal plaid", 49.99),
        ("Puffer Vest", "Lightweight warmth without bulk", 44.99),
        ("5-Pocket Stretch Jeans", "Athletic taper denim", 54.99),
        ("Linen Blend Shirt", "Breathable summer shirt", 39.99),
    ],
    "home-garden": [
        ("Bamboo Cutting Board Set", "3-piece with juice grooves", 39.99),
        ("Stainless Steel Bottle 32oz", "Double-wall insulated leak-proof", 29.99),
        ("Beeswax Candle Set", "Hand-poured natural fragrance", 24.99),
        ("Throw Pillow Covers 18x18", "Set of 4, machine washable", 32.99),
        ("Succulent Ceramic Planter Set", "Set of 3 minimalist planters", 27.99),
        ("Bamboo Toothbrush Set", "Pack of 8, biodegradable handle", 14.99),
        ("Macramé Wall Hanging", "Handcrafted boho décor", 34.99),
        ("LED String Lights 10m", "Warm white copper wire fairy lights", 17.99),
        ("Wicker Storage Basket Set", "Set of 3 with handles", 44.99),
        ("Aroma Diffuser 500ml", "Ultrasonic with 7-color LED", 37.99),
    ],
    "kitchen-dining": [
        ("Cast Iron Skillet 12-inch", "Pre-seasoned, oven safe 500°F", 44.99),
        ("Silicone Spatula Set", "Heat-resistant BPA-free set of 5", 16.99),
        ("French Press Coffee Maker 34oz", "Borosilicate glass with steel plunger", 34.99),
        ("Vegetable Spiralizer 5-Blade", "Handheld with suction base", 22.99),
        ("Mason Jar Set 16oz", "12-pack regular mouth for food storage", 19.99),
        ("Digital Kitchen Scale", "5kg capacity with tare function", 23.99),
        ("Mandoline Slicer", "6 adjustable thickness settings", 28.99),
        ("Stainless Steel Mixing Bowl Set", "5-piece nesting bowls with lids", 39.99),
        ("Reusable Silicone Food Bags", "Set of 10, dishwasher safe", 21.99),
        ("Wooden Spoon Set", "5-piece natural olive wood utensils", 18.99),
    ],
    "sports-outdoors": [
        ("Hiking Backpack 45L", "Waterproof with hydration compartment", 89.99),
        ("Foldable Trekking Poles", "Aluminum alloy with cork grips", 54.99),
        ("Compression Socks 3-Pack", "Graduated compression for recovery", 22.99),
        ("High-Density Foam Roller 36in", "Full body muscle recovery", 29.99),
        ("Running Hydration Belt", "2x 10oz bottles with phone pocket", 27.99),
        ("Camping Hammock", "Lightweight nylon with tree straps", 39.99),
        ("Dry Bag 20L", "Waterproof roll-top sack", 24.99),
        ("Headlamp 800 Lumens", "Rechargeable with red light mode", 34.99),
        ("Carabiner Clip Set 12-Pack", "D-ring locking aluminum clips", 12.99),
        ("Collapsible Water Bottle", "BPA-free 750ml foldable bottle", 17.99),
    ],
    "fitness-exercise": [
        ("Resistance Bands 5-Pack", "Latex-free with door anchor", 24.99),
        ("Adjustable Dumbbell 25lb", "Quick-change weight dial", 59.99),
        ("Non-Slip Yoga Mat 6mm", "Extra wide 72x24 with alignment lines", 34.99),
        ("Doorway Pull-Up Bar", "No-screws design with foam grips", 39.99),
        ("Ab Roller Wheel", "Double wheel with elbow support mat", 19.99),
        ("Jump Rope Speed Cable", "Ball bearing handles with tangle-free cable", 15.99),
        ("Push-Up Handles", "Rotating grip push-up stands", 18.99),
        ("Gym Gloves with Wrist Wrap", "Full palm protection, pair", 16.99),
        ("Ankle Weights 5lb Pair", "Adjustable iron sand filling", 22.99),
        ("Massage Gun Deep Tissue", "6 speeds, 4 attachments, whisper quiet", 79.99),
    ],
    "books-media": [
        ("The Art of Software Testing", "Classic guide to software quality", 39.99),
        ("Python Crash Course 3rd Ed", "Hands-on project-based introduction", 34.99),
        ("Clean Code", "Handbook of agile software craftsmanship", 44.99),
        ("The Pragmatic Programmer", "Your journey to mastery", 49.99),
        ("Designing Data-Intensive Apps", "Reliable, scalable and maintainable systems", 54.99),
        ("System Design Interview Vol 1", "Insider guide to system design", 44.99),
        ("The DevOps Handbook", "How to create world-class agility", 49.99),
        ("Refactoring 2nd Edition", "Improving the design of existing code", 54.99),
        ("Release It! 2nd Edition", "Design and deploy production-ready software", 44.99),
        ("Domain-Driven Design", "Tackling complexity in software", 59.99),
    ],
    "fiction-literature": [
        ("The Name of the Wind", "A masterful epic fantasy novel", 16.99),
        ("Dune", "The classic science fiction epic", 18.99),
        ("Project Hail Mary", "A lone astronaut saves the earth", 17.99),
        ("The Hitchhiker's Guide", "The comedic science fiction masterpiece", 14.99),
        ("Foundation", "Isaac Asimov's legendary sci-fi saga", 15.99),
        ("The Way of Kings", "Stormlight Archive Book 1", 19.99),
        ("Mistborn: The Final Empire", "Epic fantasy by Brandon Sanderson", 16.99),
        ("The Martian", "A gripping survival story on Mars", 15.99),
        ("Ender's Game", "Hugo and Nebula Award winner", 14.99),
        ("The Three-Body Problem", "A mind-bending Chinese sci-fi epic", 17.99),
    ],
}

REVIEW_TEMPLATES: dict[int, list[tuple[str, str]]] = {
    5: [
        ("Excellent product, highly recommend!", "I've been using this for a few weeks and it works exactly as described. Outstanding quality."),
        ("Exceeded my expectations!", "This product is even better than the photos suggest. Very well made and durable."),
        ("Perfect purchase!", "Exactly what I needed. Fast shipping, great packaging, and the product itself is top notch."),
    ],
    4: [
        ("Good value for the price", "Solid quality and works as advertised. Minor imperfections but nothing deal-breaking."),
        ("Solid product, will buy again", "Happy with this purchase overall. A few small things could be better but great for the price."),
        ("Works great, recommend", "Does everything I need it to do. Build quality is good and seems durable."),
    ],
    3: [
        ("Decent, nothing special", "It works as described but nothing extraordinary. Average quality for the price."),
        ("Gets the job done", "Functional product that meets the basic requirements. No wow factor but no issues either."),
        ("Okay but could be better", "Product is acceptable. Some room for improvement in quality but overall okay."),
    ],
    2: [
        ("Below average quality", "The product works but the build quality is disappointing for the price point."),
        ("Not what I expected", "Misleading product description. The quality is much lower than photos suggest."),
        ("Wouldn't buy again", "Had issues from the start. Barely functional and cheap materials throughout."),
    ],
    1: [
        ("Very disappointed", "This product failed within the first week of use. Would not recommend to anyone."),
        ("Poor quality, avoid", "Complete waste of money. The product doesn't match the description at all."),
        ("Return immediately", "Defective product right out of the box. Very poor quality control from this seller."),
    ],
}

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]

CITIES = [
    ("New York", "NY", "US", "10001"),
    ("Los Angeles", "CA", "US", "90001"),
    ("Chicago", "IL", "US", "60601"),
    ("Houston", "TX", "US", "77001"),
    ("Phoenix", "AZ", "US", "85001"),
    ("Philadelphia", "PA", "US", "19101"),
    ("San Antonio", "TX", "US", "78201"),
    ("San Diego", "CA", "US", "92101"),
    ("Dallas", "TX", "US", "75201"),
    ("San Jose", "CA", "US", "95101"),
]

COUPON_DATA = [
    ("SAVE10", 10.0, 500),
    ("WELCOME20", 20.0, 1000),
    ("FLASH15", 15.0, 100),
    ("MEMBER25", 25.0, 200),
    ("SUMMER30", 30.0, 150),
    ("DEAL5", 5.0, None),
    ("PROMO12", 12.0, 300),
    ("SPECIAL18", 18.0, 250),
    ("HOLIDAY22", 22.0, 400),
    ("BONUS8", 8.0, None),
]

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
ORDER_STATUS_WEIGHTS = [5, 10, 15, 60, 10]


# ── Helpers ────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    return name.lower().replace("&", "and").replace("'", "").replace(",", "").replace(" ", "-")


def rand_past_datetime(days_back: int = 180) -> datetime:
    delta = random.randint(0, days_back * 24 * 60 * 60)
    return datetime.now(UTC) - timedelta(seconds=delta)


def print_progress(step: str, count: int) -> None:
    print(f"  ✓ {step}: {count} records")


# ── Seeding functions ──────────────────────────────────────────────────────────

async def seed_categories(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Returns {slug: id} for all categories."""
    categories: dict[str, uuid.UUID] = {}

    for name, slug, desc, children in CATEGORY_TREE:
        parent = Category(name=name, slug=slug, description=desc, is_active=True)
        session.add(parent)
        await session.flush()
        categories[slug] = parent.id

        for child_name, child_slug, child_desc in children:
            child = Category(
                name=child_name,
                slug=child_slug,
                description=child_desc,
                parent_id=parent.id,
                is_active=True,
            )
            session.add(child)
            await session.flush()
            categories[child_slug] = child.id

    print_progress("Categories", len(categories))
    return categories


async def seed_products(
    session: AsyncSession, categories: dict[str, uuid.UUID]
) -> list[uuid.UUID]:
    """Creates NUM_PRODUCTS products and returns their IDs."""
    cat_slugs = list(PRODUCT_TEMPLATES.keys())
    product_ids: list[uuid.UUID] = []
    slug_counters: dict[str, int] = {}

    # Distribute products evenly; fill up to NUM_PRODUCTS cycling through categories
    templates_flat: list[tuple[str, tuple[str, str, float]]] = []
    for slug in cat_slugs:
        for tpl in PRODUCT_TEMPLATES[slug]:
            templates_flat.append((slug, tpl))

    # Cycle through templates until we reach NUM_PRODUCTS
    for i in range(NUM_PRODUCTS):
        cat_slug, (base_name, desc, base_price) in templates_flat[i % len(templates_flat)]

        # Add a numeric suffix to avoid duplicate slugs when cycling
        slug_counters[cat_slug] = slug_counters.get(cat_slug, 0) + 1
        suffix = slug_counters[cat_slug]
        name = f"{base_name} #{suffix}" if suffix > 1 else base_name
        slug = f"{slugify(base_name)}-{suffix}"

        # Small price variance (±15%)
        price = round(base_price * random.uniform(0.85, 1.15), 2)

        # Map category slug to a known category (prefer child if available)
        cat_id = categories.get(cat_slug) or random.choice(list(categories.values()))

        product = Product(
            name=name,
            slug=slug,
            description=desc,
            price=price,
            category_id=cat_id,
            image_url=f"https://cdn.example.com/products/{slug}.jpg",
            rating_avg=0.0,
            rating_count=0,
            is_active=True,
        )
        session.add(product)
        await session.flush()
        product_ids.append(product.id)

        # Inventory record
        qty = random.randint(10, 500)
        inv = Inventory(
            product_id=product.id,
            quantity_available=qty,
            quantity_reserved=0,
            low_stock_threshold=10,
        )
        session.add(inv)

        # Initial stock movement
        movement = InventoryMovement(
            product_id=product.id,
            delta=qty,
            movement_type="restock",
            reason="Initial seed stock",
        )
        session.add(movement)

    await session.flush()
    print_progress("Products", NUM_PRODUCTS)
    print_progress("Inventory records", NUM_PRODUCTS)
    return product_ids


async def seed_users(session: AsyncSession) -> tuple[list[uuid.UUID], list[uuid.UUID], list[uuid.UUID]]:
    """Creates admin, pool and regular users. Returns (admin_ids, pool_ids, regular_ids)."""
    hashed = hash_password(SEED_PASSWORD)
    admin_ids: list[uuid.UUID] = []
    pool_ids: list[uuid.UUID] = []
    regular_ids: list[uuid.UUID] = []

    # Admin users
    for i in range(1, NUM_ADMIN_USERS + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        user = User(
            email=f"admin{i:02d}@example.com",
            username=f"admin{i:02d}",
            hashed_password=hashed,
            full_name=f"{first} {last}",
            phone=f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}",
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        admin_ids.append(user.id)
        _add_address(session, user.id)

    # Pool users (used by the load tester's token pool)
    for i in range(1, NUM_POOL_USERS + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        user = User(
            email=f"pooluser{i:03d}@example.com",
            username=f"pooluser{i:03d}",
            hashed_password=hashed,
            full_name=f"{first} {last}",
            phone=f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}",
            role="user",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        pool_ids.append(user.id)
        _add_address(session, user.id)

    # Regular users
    for i in range(1, NUM_REGULAR_USERS + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        user = User(
            email=f"user{i:04d}@example.com",
            username=f"user{i:04d}",
            hashed_password=hashed,
            full_name=f"{first} {last}",
            role="user",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        regular_ids.append(user.id)
        _add_address(session, user.id)

    await session.flush()
    total = NUM_ADMIN_USERS + NUM_POOL_USERS + NUM_REGULAR_USERS
    print_progress("Users", total)
    return admin_ids, pool_ids, regular_ids


def _add_address(session: AsyncSession, user_id: uuid.UUID) -> None:
    city, state, country, zip_code = random.choice(CITIES)
    num = random.randint(1, 9999)
    streets = ["Main St", "Oak Ave", "Maple Dr", "Pine Rd", "Cedar Ln", "Elm St", "Park Blvd"]
    address = Address(
        user_id=user_id,
        line1=f"{num} {random.choice(streets)}",
        city=city,
        state=state,
        country=country,
        zip_code=zip_code,
        is_default=True,
    )
    session.add(address)


async def seed_coupons(session: AsyncSession) -> None:
    for code, pct, max_uses in COUPON_DATA:
        expires = datetime.now(UTC) + timedelta(days=random.randint(30, 365))
        coupon = Coupon(
            code=code,
            discount_pct=pct,
            max_uses=max_uses,
            uses_count=random.randint(0, 20),
            expires_at=expires,
            is_active=True,
        )
        session.add(coupon)
    await session.flush()
    print_progress("Coupons", NUM_COUPONS)


async def seed_orders(
    session: AsyncSession,
    buyer_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """Creates orders and returns [(order_id, user_id, product_id), ...] for review seeding."""
    # Fetch addresses mapped by user_id
    result = await session.execute(select(Address).where(Address.user_id.in_(buyer_ids)))
    address_map: dict[uuid.UUID, uuid.UUID] = {a.user_id: a.id for a in result.scalars().all()}

    order_product_pairs: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = []

    for _ in range(NUM_ORDERS):
        user_id = random.choice(buyer_ids)
        address_id = address_map.get(user_id)
        if address_id is None:
            continue

        n_items = random.randint(1, 3)
        chosen_products = random.sample(product_ids, min(n_items, len(product_ids)))

        # Fetch product prices
        result = await session.execute(select(Product).where(Product.id.in_(chosen_products)))
        products = {p.id: p for p in result.scalars().all()}

        subtotal = sum(products[pid].price * random.randint(1, 3) for pid in chosen_products)
        tax = round(subtotal * 0.08, 2)
        total = round(subtotal + tax, 2)

        status = random.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS, k=1)[0]
        created = rand_past_datetime(180)

        order = Order(
            user_id=user_id,
            status=status,
            subtotal=round(subtotal, 2),
            tax=tax,
            discount=0.0,
            total=total,
            shipping_address_id=address_id,
            created_at=created,
            updated_at=created,
        )
        session.add(order)
        await session.flush()

        for pid in chosen_products:
            p = products[pid]
            qty = random.randint(1, 3)
            item = OrderItem(
                order_id=order.id,
                product_id=pid,
                product_name=p.name,
                quantity=qty,
                unit_price=p.price,
            )
            session.add(item)
            order_product_pairs.append((order.id, user_id, pid))

        # Payment
        pay_status = "approved" if status not in ("cancelled",) else random.choice(["approved", "rejected"])
        gateway_ref = f"GW-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment(
            order_id=order.id,
            status=pay_status,
            amount=total,
            gateway_ref=gateway_ref,
            failure_reason="Card declined by issuer" if pay_status == "rejected" else None,
            created_at=created,
            updated_at=created,
        )
        session.add(payment)

    await session.flush()
    print_progress("Orders", NUM_ORDERS)
    return order_product_pairs


async def seed_reviews(
    session: AsyncSession,
    order_product_pairs: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]],
) -> None:
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    count = 0

    random.shuffle(order_product_pairs)

    for order_id, user_id, product_id in order_product_pairs:
        if count >= NUM_REVIEWS:
            break
        pair = (product_id, user_id)
        if pair in seen:
            continue
        seen.add(pair)

        rating = random.choices([5, 4, 3, 2, 1], weights=[40, 30, 15, 10, 5], k=1)[0]
        title, body = random.choice(REVIEW_TEMPLATES[rating])

        review = Review(
            product_id=product_id,
            user_id=user_id,
            order_id=order_id,
            rating=rating,
            title=title,
            body=body,
            helpful_votes=random.randint(0, 50),
        )
        session.add(review)
        count += 1

    await session.flush()

    # Recalculate rating_avg / rating_count for each reviewed product
    reviewed_products = {pid for _, _, pid in order_product_pairs[:count]}
    for pid in reviewed_products:
        result = await session.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == pid)
        )
        avg, cnt = result.one()
        if avg is not None:
            await session.execute(
                Product.__table__.update()
                .where(Product.id == pid)
                .values(rating_avg=round(float(avg), 2), rating_count=cnt)
            )

    print_progress("Reviews", count)


# ── Main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("🌱 Seeding database…\n")

    async with AsyncSessionLocal() as session:
        # Idempotency check
        result = await session.execute(select(func.count()).select_from(Category))
        existing_count: int = result.scalar_one()
        if existing_count > 0:
            print(f"Database already seeded ({existing_count} categories found). Skipping.")
            return

        try:
            categories = await seed_categories(session)
            product_ids = await seed_products(session, categories)
            admin_ids, pool_ids, regular_ids = await seed_users(session)
            await seed_coupons(session)

            buyer_ids = pool_ids + regular_ids
            order_product_pairs = await seed_orders(session, buyer_ids, product_ids)
            await seed_reviews(session, order_product_pairs)

            await session.commit()
            print("\n✅ Seed complete.")
            print(f"   Categories : 10")
            print(f"   Products   : {NUM_PRODUCTS}")
            print(f"   Admin users: {NUM_ADMIN_USERS}  (admin01@example.com … admin05@example.com)")
            print(f"   Pool users : {NUM_POOL_USERS}   (pooluser001@example.com … pooluser050@example.com)")
            print(f"   Regular    : {NUM_REGULAR_USERS}")
            print(f"   Coupons    : {NUM_COUPONS}")
            print(f"   Orders     : {NUM_ORDERS}")
            print(f"   Password   : {SEED_PASSWORD}")
        except Exception as exc:
            await session.rollback()
            print(f"\n❌ Seed failed: {exc}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
