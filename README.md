# FastAPI Benchmark

Prueba de rendimiento de extremo a extremo para FastAPI. Consiste en una API de e-commerce async completa y un load tester con dashboard en tiempo real, diseñados para correr en dos PCs distintas dentro de la misma LAN.

---

## Arquitectura

```
[PC Cliente — Ryzen 5 5500 / 24 GB RAM]          [PC Servidor — i5-8250U / 12 GB RAM]
┌──────────────────────────────────────┐          ┌───────────────────────────────┐
│  load_tester/runner.py               │          │  api/  (Gunicorn + Uvicorn)   │
│  · Genera tráfico HTTP async         │──HTTP───►│  Puerto 8000                  │
│  · Colecta métricas en memoria       │◄─HTTP────│                               │
│                                      │          └───────────────────────────────┘
│  load_tester/ui/  (FastAPI + HTMX)   │
│  · Dashboard en tiempo real          │
│  · Puerto 8001 (accesible en LAN)    │
└──────────────────────────────────────┘
```

La API no sabe que existe un tester. Las métricas (latencia, RPS, errores) las calcula el cliente porque es quien conoce el tiempo real de extremo a extremo.

---

## Requisitos

- Python 3.13+
- [UV](https://docs.astral.sh/uv/) como gestor de paquetes
- Ambas PCs en la misma red local (LAN)
- Linux/macOS en la PC servidor para usar Gunicorn con múltiples workers
  - En Windows, Uvicorn corre con un solo worker (usar solo para desarrollo local)

---

## Instalación

### Clonar el repositorio (en ambas PCs)

```bash
git clone <url-del-repo>
cd fastapi-benchmark
```

### PC Servidor — instalar dependencias de la API

```bash
uv sync --group api
```

### PC Cliente — instalar dependencias del load tester

```bash
uv sync --group tester --group dev
```

### Configuración

```bash
cp .env.example .env
```

Editar `.env` según el entorno:

- En la PC **servidor**: ajustar `DATABASE_URL`, `SECRET_KEY`, `API_WORKERS`.
- En la PC **cliente**: ajustar `API_BASE_URL` con la IP del servidor en la LAN.

---

## Uso

### 1. Preparar la base de datos (PC servidor)

```bash
# Crear las tablas
uv run alembic upgrade head

# Poblar con datos sintéticos (categorías, productos, usuarios, órdenes)
uv run seed-db
```

El seed usa un generador procedural de catálogo tipo **base item + prefijo + sufijo** para crear productos sintéticos pero ordenados.

### 2. Levantar la API (PC servidor)

**Linux/macOS — producción (múltiples workers):**

```bash
uv run gunicorn api.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

**Windows o desarrollo local (un worker con hot-reload):**

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

La API estará disponible en `http://<ip-servidor>:8000`.
La documentación interactiva en `http://<ip-servidor>:8000/docs`.

### 3. Verificar el sistema end-to-end (PC cliente)

Antes de lanzar el test completo, comprueba que la API responde correctamente en todos sus endpoints:

```bash
# Verificación rápida de conectividad
uv run python scripts/check_connectivity.py

# Verificación completa (ejercita el flujo de compra de extremo a extremo)
uv run e2e-check
```

El script `e2e_check.py` registra un usuario temporal, añade un producto al carrito, hace checkout y verifica las órdenes. Sale con código 1 si algún paso falla.

### 4. Ejecutar el load tester y abrir el dashboard (PC cliente)

```bash
uv run start-tester
```

El runner lanza el test y el dashboard simultáneamente.
Abrir en el navegador: `http://localhost:8001` (o la IP del cliente desde otra PC).

Desde el dashboard puedes ajustar antes de iniciar la prueba el escenario, la cantidad de usuarios simultáneos, el token pool, think time, timeouts y los parámetros de ramp-up / sustained / spike.

---

## Configuración del Test

Todos los parámetros se controlan desde `.env` sin tocar el código:

| Variable | Descripción | Default |
|---|---|---|
| `API_BASE_URL` | IP y puerto de la API | `http://192.168.1.100:8000` |
| `SCENARIO` | `ramp_up`, `spike`, `sustained`, `combined` | `combined` |
| `MAX_WORKERS` | Máximo de usuarios virtuales concurrentes | `200` |
| `DURATION_SECONDS` | Duración total del test | `300` |
| `THINK_TIME_MIN_MS` | Pausa mínima entre pasos de un flujo | `50` |
| `THINK_TIME_MAX_MS` | Pausa máxima entre pasos de un flujo | `300` |
| `REQUEST_TIMEOUT_S` | Timeout por request | `10` |
| `TOKEN_POOL_SIZE` | Usuarios pre-autenticados en el pool | `50` |

---

## Escenarios de Carga

| Escenario | Descripción |
|---|---|
| `ramp_up` | Incrementa workers gradualmente hasta el máximo. Identifica el punto de quiebre. |
| `spike` | Pico súbito de carga. Prueba la resiliencia ante tráfico inesperado. |
| `sustained` | Carga constante por un período largo. Detecta degradación gradual. |
| `combined` | Ejecuta los tres en secuencia. El test más completo. |

---

## Flujos de Usuario Simulados

| Flujo | Descripción | Peso |
|---|---|---|
| `browse_and_buy` | Login → catálogo → carrito → checkout → pago → reseña | 30% |
| `browse_only` | Login → navegar productos → leer reseñas | 60% |
| `admin_flow` | Gestión de órdenes, stock y productos | 10% |

---

## Métricas del Dashboard

- RPS en tiempo real (requests por segundo)
- Latencia P50, P95, P99
- Tasa de error (4xx / 5xx / timeout)
- Throughput (KB/s)
- Workers activos
- Histograma de distribución de latencias
- Desglose por endpoint (tabla ordenable)
- Log de errores recientes

Al finalizar el test, el reporte completo se descarga desde `http://localhost:8001/report?format=json` o `?format=csv`.

---

## Cambiar SQLite → PostgreSQL

Solo requiere cambiar una línea en `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ecommerce
```

Y volver a ejecutar las migraciones:

```bash
uv run alembic upgrade head
uv run seed-db
```

No hay ningún cambio en el código de la aplicación.

---

## Estructura del Proyecto

```
fastapi-benchmark/
├── api/                    # E-commerce API (PC servidor)
│   ├── core/               # Config, BD, seguridad, dependencias
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic schemas
│   ├── routers/            # Un router por dominio
│   ├── services/           # Lógica de negocio
│   ├── tasks/              # Background tasks
│   ├── middleware/         # Timing, request ID
│   └── main.py
├── load_tester/            # Load tester (PC cliente)
│   ├── core/               # Config, cliente HTTP, métricas, auth pool
│   ├── scenarios/          # ramp_up, spike, sustained, combined
│   ├── flows/              # Flujos de usuario realistas
│   ├── ui/                 # Dashboard FastAPI + HTMX
│   └── runner.py
├── scripts/
│   ├── seed_db.py          # Pobla la BD con datos realistas
│   └── check_connectivity.py
├── docs/                   # Documentación de diseño
├── results/                # Reportes generados (JSON/CSV)
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Hardware del Benchmark

| Rol | PC | CPU | RAM |
|---|---|---|---|
| Servidor (API) | PC 2 | Intel Core i5-8250U (4C/8T) | 12 GB DDR4 |
| Cliente (tester) | PC 1 | AMD Ryzen 5 5500 (6C/12T) | 24 GB DDR4 |

El cliente tiene más capacidad que el servidor de forma intencional: el objetivo es crear un cuello de botella en el servidor y observar cómo se comporta bajo presión sostenida.

---

## Resultados Esperados

Los rangos siguientes corresponden al hardware documentado con **SQLite** y **4 workers Gunicorn**. Con PostgreSQL los valores de escritura mejoran entre un 2x y 4x.

### RPS por tipo de operación

| Operación | RPS esperado (SQLite) | RPS esperado (PostgreSQL) |
|---|---|---|
| `GET /products/` (listado) | 300 – 500 | 600 – 1000 |
| `GET /products/?search=…` | 200 – 350 | 400 – 700 |
| `POST /auth/login` | 150 – 250 | 300 – 500 |
| `POST /cart/items` | 80 – 150 | 200 – 400 |
| `POST /orders/` (checkout) | 40 – 80 | 120 – 250 |
| Carga mixta (flujos combinados) | **100 – 200** | **250 – 450** |

### Latencias esperadas (carga mixta, 50 workers)

| Percentil | SQLite | PostgreSQL |
|---|---|---|
| P50 | 8 – 25 ms | 5 – 15 ms |
| P95 | 80 – 200 ms | 40 – 100 ms |
| P99 | 200 – 600 ms | 80 – 250 ms |

### Punto de saturación estimado

Con SQLite, el servidor alcanza el límite de throughput útil alrededor de **60 – 80 workers concurrentes**. Por encima, la latencia P99 se dispara pero el RPS se mantiene estable o baja levemente. Esta es exactamente la zona que explora el escenario `ramp_up`.

### Notas de interpretación

- El cuello de botella con SQLite suele ser el lock de escritura en disco, no la CPU del servidor.
- El cuello de botella con PostgreSQL suele ser la CPU del i5-8250U alrededor de 60–70% de uso.
- La tasa de error esperada en condiciones normales es < 1% (solo errores de stock agotado y pagos rechazados simulados).
- Un P99 > 2000 ms o error_rate > 5% indica que el servidor está completamente saturado.
