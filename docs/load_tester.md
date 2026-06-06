# Load Tester — Requisitos Funcionales

## Descripción General

El load tester es un módulo Python que corre en la PC cliente (Ryzen 5 5500) y tiene como objetivo generar tráfico HTTP realista contra la API del e-commerce para medir sus límites de rendimiento. No es un bombardeo simple de requests idénticos: simula usuarios reales ejecutando flujos completos de negocio.

Está compuesto por dos partes que corren simultáneamente:

1. **Runner**: el motor de carga. Orquesta workers async, ejecuta flujos de usuario y colecta métricas.
2. **Dashboard UI**: un servidor web liviano que expone las métricas en tiempo real (documentado en `dashboard.md`).

---

## Flujos de Usuario (`flows/`)

Un flujo es una secuencia de requests que imita lo que haría un usuario real. Cada worker del runner ejecuta flujos de forma continua durante la duración del test.

### Flujo: Browse and Buy

El flujo más completo y representativo. Simula un usuario que llega, navega, compra y se va.

1. Registrar cuenta nueva (o hacer login si ya existe).
2. Listar categorías y elegir una aleatoriamente.
3. Buscar productos en esa categoría con filtros aleatorios.
4. Ver el detalle de 1-3 productos.
5. Agregar 1-2 productos al carrito.
6. Ver el carrito.
7. Hacer checkout (crear orden).
8. Procesar el pago.
9. Consultar el estado de la orden.
10. Dejar una reseña en uno de los productos comprados.

Entre cada paso hay un delay configurable (por defecto entre 50ms y 300ms) para simular el "think time" humano.

### Flujo: Browse Only

Simula visitantes que navegan pero no compran. Genera carga de lectura pura.

1. Login (o usar token en pool).
2. Listar productos con distintos filtros y ordenamientos.
3. Ver detalles de varios productos.
4. Leer reseñas de productos.
5. Buscar por texto.

Este flujo es más liviano y se usa para simular la proporción realista de usuarios: la gran mayoría navega sin comprar.

### Flujo: Admin Operations

Simula las operaciones de backoffice que ocurren en producción concurrentemente con el tráfico de usuarios.

1. Login como administrador.
2. Consultar órdenes pendientes.
3. Actualizar estados de órdenes.
4. Ajustar stock de productos.
5. Ver reportes de stock bajo.
6. Crear o actualizar productos.

---

## Escenarios de Carga (`scenarios/`)

Un escenario define cuántos workers corren, durante cuánto tiempo y con qué distribución de flujos.

### Ramp Up

Incrementa la carga gradualmente desde 0 hasta el máximo configurado. Útil para identificar el punto exacto en que la API empieza a degradarse.

- Comienza con N workers.
- Cada intervalo de tiempo (configurable) agrega un incremento de workers.
- Registra en qué cantidad de workers aparecen los primeros errores y cuándo la latencia P95 supera el umbral de alerta.

### Spike

Introduce un pico súbito de carga para probar la resiliencia ante tráfico inesperado.

- Corre con carga base normal durante un tiempo.
- De golpe eleva los workers al máximo configurado por un período corto.
- Vuelve a la carga base.
- Observa cuánto tarda la API en recuperarse (si lo hace).

### Sustained Load

Mantiene una carga constante y alta por un período prolongado. Útil para detectar degradación gradual (memory leaks, agotamiento de conexiones a BD, etc.).

- Mantiene una cantidad fija de workers durante todo el test.
- La duración es la más larga de todos los escenarios (configurable, por defecto 10-30 minutos).

### Combined

Orquesta los tres escenarios anteriores en secuencia con períodos de reposo entre ellos. Genera el test más completo y representativo.

---

## Colector de Métricas (`core/metrics.py`)

Es el componente central que recibe el resultado de cada request y acumula las estadísticas en memoria. El dashboard las lee de aquí vía SSE.

### Métricas por Request

Por cada request completado (exitoso o fallido), se registra:

- Timestamp de inicio y fin.
- Método HTTP y endpoint (path normalizado, sin IDs variables).
- Código de respuesta HTTP.
- Latencia en milisegundos.
- Tamaño de la respuesta en bytes.
- Worker ID que lo ejecutó.
- Flujo al que pertenece.

### Métricas Agregadas en Tiempo Real

El colector mantiene ventanas deslizantes de tiempo (por defecto los últimos 5 segundos) para calcular:

- **RPS** (Requests Per Second): requests completados en la ventana actual.
- **Latencia P50, P95, P99**: percentiles calculados sobre la ventana deslizante.
- **Tasa de error**: porcentaje de requests con código >= 400 o timeout.
- **Throughput**: bytes recibidos por segundo.
- **Workers activos**: cantidad de workers concurrentes en ese momento.

### Métricas Acumuladas del Test Completo

Al finalizar el test, el colector produce un reporte consolidado:

- Total de requests enviados y completados.
- Total de errores desglosados por tipo (timeout, 4xx, 5xx, connection error).
- Distribución de latencias (histograma con buckets configurables).
- Latencia mínima, máxima, promedio y percentiles P50/P95/P99 del test completo.
- RPS promedio y RPS pico.
- Endpoint más lento y más rápido (por P95).
- Endpoint con mayor tasa de error.
- Duración total del test.
- Número de workers máximo alcanzado.

El reporte final se exporta automáticamente a JSON y CSV al terminar el test.

---

## Gestión de Tokens (`core/auth.py`)

Para evitar que el costo del login contamine las métricas de rendimiento de los endpoints de negocio, el load tester mantiene un **pool de tokens** precargado antes de iniciar el test.

- Al arrancar, se crean N usuarios de prueba en la API (o se usan los existentes si ya fueron creados en un run anterior).
- Se hace login con cada uno y se almacenan los tokens en el pool.
- Los workers toman tokens del pool. Si un token expira, el worker hace refresh automáticamente en background.
- Los requests de login/registro que ocurren como parte de los flujos sí se miden, pero los logins de inicialización no.

---

## Cliente HTTP (`core/client.py`)

Wrapper sobre `httpx.AsyncClient` con comportamiento configurado para el test:

- Timeout configurable (por defecto 10 segundos por request).
- Manejo de errores que distingue entre timeout, connection error y respuesta HTTP de error.
- Reintentos opcionales (por defecto 0, para que los fallos se cuenten como fallos).
- Headers comunes precargados (User-Agent, Accept, Content-Type).
- Soporte para adjuntar token JWT automáticamente.

---

## Runner Principal (`runner.py`)

El entrypoint del load tester. Orquesta todo el sistema.

Al ejecutarse:

1. Lee la configuración del escenario a correr (desde argumentos de línea de comandos o variables de entorno).
2. Verifica conectividad con la API antes de arrancar.
3. Inicializa el pool de tokens.
4. Lanza el servidor del dashboard en un thread separado.
5. Imprime la URL del dashboard en la consola.
6. Ejecuta el escenario seleccionado.
7. Al finalizar, genera el reporte y lo guarda en `results/`.

---

## Configuración

Todos los parámetros son configurables sin tocar el código, mediante variables de entorno o un archivo `.env`:

| Variable | Descripción | Default |
|---|---|---|
| `API_BASE_URL` | URL base de la API a testear | `http://localhost:8000` |
| `SCENARIO` | Escenario a ejecutar | `combined` |
| `MAX_WORKERS` | Máximo de workers concurrentes | `100` |
| `DURATION_SECONDS` | Duración del test | `300` |
| `THINK_TIME_MIN_MS` | Delay mínimo entre pasos de un flujo | `50` |
| `THINK_TIME_MAX_MS` | Delay máximo entre pasos de un flujo | `300` |
| `REQUEST_TIMEOUT_S` | Timeout por request | `10` |
| `TOKEN_POOL_SIZE` | Cantidad de usuarios en el pool | `50` |
| `DASHBOARD_PORT` | Puerto del dashboard UI | `8001` |
| `RESULTS_DIR` | Directorio donde guardar reportes | `results/` |
