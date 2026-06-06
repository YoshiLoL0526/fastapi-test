# Roadmap de Implementación

Estado de cada tarea actualizado a medida que se completa. Las tareas están ordenadas por dependencia: cada grupo puede comenzar solo cuando el anterior está completo.

**Leyenda**: ⬜ Pendiente · 🔄 En progreso · ✅ Completado

---

## Fase 0 — Documentación y Estructura

- ✅ `docs/architecture.md` — visión general del sistema
- ✅ `docs/api.md` — requisitos funcionales del e-commerce API
- ✅ `docs/load_tester.md` — requisitos funcionales del load tester
- ✅ `docs/dashboard.md` — requisitos funcionales del dashboard UI
- ✅ `docs/database.md` — diseño de la base de datos
- ✅ `docs/roadmap.md` — este archivo
- ✅ `README.md` — guía de instalación, uso y resultados esperados
- ✅ Estructura de carpetas base del proyecto
- ✅ `pyproject.toml` con todas las dependencias
- ✅ `.env.example` con todas las variables configurables
- ✅ `.gitignore`

---

## Fase 1 — Core del API

- ✅ `api/core/config.py` — Settings con pydantic-settings
- ✅ `api/core/database.py` — Motor async, Session factory, función de cierre
- ✅ `api/core/security.py` — Hash de contraseñas, JWT encode/decode
- ✅ `api/core/dependencies.py` — `get_db`, `get_current_user`, `require_admin`
- ✅ `api/middleware/timing.py` — Header `X-Process-Time`
- ✅ `api/middleware/request_id.py` — Header `X-Request-ID`
- ✅ `api/main.py` — Instancia FastAPI, registro de routers y middleware

---

## Fase 2 — Modelos y Migraciones

- ✅ `api/models/user.py` — `User`, `RefreshToken`, `Address`
- ✅ `api/models/product.py` — `Product`, `Category`
- ✅ `api/models/inventory.py` — `Inventory`, `InventoryMovement`
- ✅ `api/models/cart.py` — `Cart`, `CartItem`, `Coupon`
- ✅ `api/models/order.py` — `Order`, `OrderItem`
- ✅ `api/models/payment.py` — `Payment`
- ✅ `api/models/review.py` — `Review`
- ✅ Configuración de Alembic (`alembic.ini`, `env.py`)
- ✅ Migración inicial (`alembic revision --autogenerate`)

---

## Fase 3 — Schemas Pydantic

- ✅ `api/schemas/user.py`
- ✅ `api/schemas/product.py`
- ✅ `api/schemas/category.py`
- ✅ `api/schemas/cart.py`
- ✅ `api/schemas/order.py`
- ✅ `api/schemas/payment.py`
- ✅ `api/schemas/review.py`
- ✅ `api/schemas/inventory.py`
- ✅ `api/schemas/common.py` — respuestas paginadas, mensajes de error

---

## Fase 4 — Servicios y Lógica de Negocio

- ✅ `api/services/auth.py` — login, registro, refresh, logout
- ✅ `api/services/product.py` — búsqueda, filtros, paginación
- ✅ `api/services/cart.py` — agregar, actualizar, vaciar, aplicar cupón
- ✅ `api/services/order.py` — checkout, transición de estados
- ✅ `api/services/payment.py` — procesamiento simulado con delay
- ✅ `api/services/inventory.py` — reserva atómica de stock
- ✅ `api/services/review.py` — CRUD + validación de compra verificada
- ✅ `api/tasks/background.py` — recálculo de rating, notificaciones, stock

---

## Fase 5 — Routers

- ✅ `api/routers/auth.py`
- ✅ `api/routers/users.py`
- ✅ `api/routers/products.py`
- ✅ `api/routers/categories.py`
- ✅ `api/routers/cart.py`
- ✅ `api/routers/orders.py`
- ✅ `api/routers/payments.py`
- ✅ `api/routers/inventory.py`
- ✅ `api/routers/reviews.py`
- ✅ `api/routers/uploads.py`
- ✅ `api/routers/websockets.py`
- ✅ `api/routers/health.py`

---

## Fase 6 — Script de Seed

- ✅ `scripts/seed_db.py` — datos realistas (categorías, productos, usuarios, órdenes, reseñas)
- ✅ `scripts/check_connectivity.py` — verifica acceso a la API antes del test

---

## Fase 7 — Core del Load Tester

- ⬜ `load_tester/core/config.py`
- ⬜ `load_tester/core/client.py` — wrapper httpx async
- ⬜ `load_tester/core/metrics.py` — colector con ventanas deslizantes
- ⬜ `load_tester/core/auth.py` — pool de tokens

---

## Fase 8 — Flujos y Escenarios

- ⬜ `load_tester/flows/browse_and_buy.py`
- ⬜ `load_tester/flows/browse_only.py`
- ⬜ `load_tester/flows/admin_flow.py`
- ⬜ `load_tester/scenarios/base.py`
- ⬜ `load_tester/scenarios/ramp_up.py`
- ⬜ `load_tester/scenarios/spike.py`
- ⬜ `load_tester/scenarios/sustained.py`
- ⬜ `load_tester/scenarios/combined.py`
- ⬜ `load_tester/runner.py`

---

## Fase 9 — Dashboard UI

- ⬜ `load_tester/ui/main.py` — servidor FastAPI del dashboard
- ⬜ `load_tester/ui/templates/index.html` — HTMX + Chart.js
- ⬜ Endpoint SSE `/stream`
- ⬜ Endpoint de descarga `/report`

---

## Fase 10 — Integración Final

- ⬜ Verificación end-to-end: API + seed + load tester + dashboard
- ⬜ Prueba en LAN entre las dos PCs
- ⬜ Ajuste de parámetros según hardware real
- ⬜ Documentación de resultados en `README.md`
