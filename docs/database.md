# Base de Datos — Diseño y Requisitos

## Descripción General

La capa de datos está construida sobre **SQLAlchemy 2.x en modo async**, lo que permite que todas las operaciones de BD sean no bloqueantes y se integren con el event loop de FastAPI sin overhead.

El diseño prioriza la **intercambiabilidad entre motores**: cambiar de SQLite a PostgreSQL es solo un cambio de variable de entorno (`DATABASE_URL`) y de driver (`aiosqlite` → `asyncpg`). No hay SQL nativo ni características específicas de un motor en el código de la aplicación.

Las migraciones se gestionan con **Alembic**, que mantiene el historial de cambios del esquema y permite aplicarlos o revertirlos de forma controlada.

---

## Estrategia de Conexión

### SQLite (desarrollo y benchmark inicial)

```
DATABASE_URL=sqlite+aiosqlite:///./ecommerce.db
```

- Un solo archivo local.
- Sin configuración adicional.
- Limitado en concurrencia (WAL mode activado para mejorar lecturas concurrentes).
- Ideal para establecer una línea base de rendimiento.

### PostgreSQL (benchmark de producción)

```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/ecommerce
```

- Pool de conexiones configurado con `min_size` y `max_size` ajustables.
- Soporte real de concurrencia y transacciones paralelas.
- Permite comparar directamente el impacto del motor en los resultados del benchmark.

El cambio entre motores no requiere modificar ninguna línea de código de la aplicación.

---

## Entidades y Relaciones

### `users`

Almacena los datos de los usuarios registrados.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `email` | VARCHAR(255) | Único, indexado |
| `username` | VARCHAR(100) | Único |
| `hashed_password` | VARCHAR | Hash bcrypt |
| `full_name` | VARCHAR(200) | Nombre completo |
| `phone` | VARCHAR(20) | Opcional |
| `role` | ENUM | `user` o `admin` |
| `is_active` | BOOLEAN | Para baja lógica |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `refresh_tokens`

Permite invalidar sesiones individuales sin revocar todos los tokens.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `token` | VARCHAR | Indexado |
| `expires_at` | TIMESTAMP | |
| `revoked` | BOOLEAN | |
| `created_at` | TIMESTAMP | |

### `addresses`

Dirección de envío asociada a un usuario.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `line1` | VARCHAR | |
| `line2` | VARCHAR | Opcional |
| `city` | VARCHAR | |
| `state` | VARCHAR | |
| `country` | VARCHAR(2) | Código ISO |
| `zip_code` | VARCHAR | |
| `is_default` | BOOLEAN | |

### `categories`

Árbol de categorías con soporte para jerarquía simple (un nivel de anidamiento).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `name` | VARCHAR(100) | |
| `slug` | VARCHAR(100) | Único, para URLs |
| `description` | TEXT | Opcional |
| `parent_id` | UUID | FK → categories (nullable) |
| `is_active` | BOOLEAN | |

### `products`

El catálogo de productos.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `name` | VARCHAR(300) | Indexado para búsqueda |
| `slug` | VARCHAR(300) | Único |
| `description` | TEXT | |
| `price` | NUMERIC(10,2) | |
| `category_id` | UUID | FK → categories |
| `image_url` | VARCHAR | URL de la imagen principal |
| `rating_avg` | NUMERIC(3,2) | Desnormalizado, recalculado por background task |
| `rating_count` | INTEGER | Desnormalizado |
| `is_active` | BOOLEAN | Baja lógica |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `inventory`

Stock de cada producto. Separado de `products` para facilitar locking atómico bajo concurrencia.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `product_id` | UUID | FK → products, único |
| `quantity_available` | INTEGER | Stock disponible para venta |
| `quantity_reserved` | INTEGER | Reservado por órdenes pendientes |
| `low_stock_threshold` | INTEGER | Umbral de alerta |
| `updated_at` | TIMESTAMP | |

### `inventory_movements`

Log de auditoría de todos los cambios de stock.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `product_id` | UUID | FK → products |
| `delta` | INTEGER | Positivo (entrada) o negativo (salida) |
| `movement_type` | ENUM | `sale`, `restock`, `reservation`, `release`, `adjustment` |
| `reason` | TEXT | Descripción opcional |
| `created_at` | TIMESTAMP | |

### `carts`

Carrito activo de cada usuario. Solo puede haber uno activo por usuario.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users, único |
| `coupon_code` | VARCHAR | Opcional |
| `discount_pct` | NUMERIC(5,2) | Porcentaje de descuento aplicado |
| `updated_at` | TIMESTAMP | |

### `cart_items`

Ítems dentro de un carrito.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `cart_id` | UUID | FK → carts |
| `product_id` | UUID | FK → products |
| `quantity` | INTEGER | |
| `unit_price` | NUMERIC(10,2) | Precio en el momento de agregarlo |

### `orders`

Registro de cada compra finalizada.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `status` | ENUM | `pending`, `processing`, `shipped`, `delivered`, `cancelled`, `refunded` |
| `subtotal` | NUMERIC(10,2) | |
| `tax` | NUMERIC(10,2) | |
| `discount` | NUMERIC(10,2) | |
| `total` | NUMERIC(10,2) | |
| `shipping_address_id` | UUID | FK → addresses |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `order_items`

Snapshot de los productos comprados al momento del checkout.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | FK → orders |
| `product_id` | UUID | FK → products |
| `product_name` | VARCHAR | Snapshot del nombre |
| `quantity` | INTEGER | |
| `unit_price` | NUMERIC(10,2) | Snapshot del precio |

### `payments`

Registro de intentos de pago.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | FK → orders |
| `status` | ENUM | `pending`, `approved`, `rejected`, `refunded` |
| `amount` | NUMERIC(10,2) | |
| `gateway_ref` | VARCHAR | ID ficticio de la pasarela |
| `failure_reason` | TEXT | Mensaje en caso de rechazo |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `reviews`

Reseñas de productos por usuarios que los compraron.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `product_id` | UUID | FK → products |
| `user_id` | UUID | FK → users |
| `order_id` | UUID | FK → orders (verifica compra) |
| `rating` | SMALLINT | 1 a 5 |
| `title` | VARCHAR(200) | |
| `body` | TEXT | |
| `helpful_votes` | INTEGER | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

Índice único sobre `(product_id, user_id)` para garantizar una sola reseña por usuario por producto.

### `coupons`

Códigos de descuento aplicables al carrito.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `code` | VARCHAR(50) | Único, indexado |
| `discount_pct` | NUMERIC(5,2) | |
| `max_uses` | INTEGER | Nullable = ilimitado |
| `uses_count` | INTEGER | |
| `expires_at` | TIMESTAMP | Nullable |
| `is_active` | BOOLEAN | |

---

## Índices

Los siguientes índices son críticos para el rendimiento bajo carga:

- `products.category_id` — filtros por categoría
- `products.name` — búsqueda por texto (FTS en PostgreSQL, LIKE en SQLite)
- `products.rating_avg` — ordenamiento por rating
- `orders.user_id` — historial de órdenes por usuario
- `orders.status` — filtros de admin
- `order_items.order_id` — detalle de orden
- `reviews.product_id` — reseñas por producto
- `cart_items.cart_id` — contenido del carrito
- `inventory.product_id` — stock por producto
- `refresh_tokens.token` — validación de tokens

---

## Seeding de Datos

Antes de ejecutar el benchmark, la base de datos se puebla con datos realistas mediante el script `scripts/seed_db.py`:

- 10 categorías con estructura padre/hijo
- 500 productos distribuidos entre categorías
- 1000 usuarios de prueba (50 son parte del pool del tester)
- 5 usuarios administradores
- Stock inicial aleatorio entre 10 y 500 unidades por producto
- 200 órdenes históricas con sus pagos e ítems
- 1000 reseñas distribuidas entre productos y usuarios
- 10 cupones de descuento activos

El seeding es idempotente: puede ejecutarse múltiples veces sin duplicar datos.
