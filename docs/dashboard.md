# Dashboard UI — Requisitos Funcionales

## Descripción General

El dashboard es una interfaz web en tiempo real que corre en la PC cliente junto al runner del load tester. Su propósito es visualizar las métricas del test mientras este ocurre, sin necesidad de esperar a que termine.

Está construido con **FastAPI** como servidor, **HTMX** para actualizaciones dinámicas del DOM sin JavaScript complejo, y **Chart.js** para las gráficas animadas. La comunicación entre el servidor del dashboard y el navegador usa **Server-Sent Events (SSE)**, que permiten un flujo continuo de datos del servidor al cliente sin polling.

Es accesible desde cualquier dispositivo en la misma LAN apuntando a `http://<ip-cliente>:8001`.

---

## Arquitectura Interna

```
runner.py
    │
    ▼ escribe en memoria compartida
MetricsStore (singleton)
    │
    ▼ lee cada segundo
dashboard/main.py  (FastAPI)
    │
    ├── GET /           → sirve el HTML principal
    ├── GET /stream     → SSE: emite JSON de métricas cada segundo
    └── GET /report     → descarga el reporte final en JSON/CSV
```

El dashboard no hace requests a la API de e-commerce. Solo lee el `MetricsStore` que el runner actualiza en tiempo real. Esto significa que el dashboard no añade carga al servidor siendo testeado.

---

## Interfaz Visual

### Panel Superior — Estado del Test

Una barra horizontal con el estado general visible de un vistazo:

- **Estado**: `Idle` / `Running` / `Finished`
- **Escenario activo**: nombre del escenario en ejecución
- **Tiempo transcurrido** y tiempo restante (si aplica)
- **Workers activos** en el momento actual
- **Botón de control**: Start / Stop (opcional en primera versión)

### Sección Principal — Métricas en Tiempo Real

Cuatro tarjetas de métricas clave actualizadas cada segundo:

| Tarjeta | Contenido |
|---|---|
| RPS | Requests por segundo actuales con sparkline de los últimos 60s |
| Latencia P95 | Valor actual en ms con indicador de color (verde/amarillo/rojo) |
| Tasa de Error | Porcentaje actual con tendencia |
| Throughput | KB/s recibidos del servidor |

### Gráficas Principales

**Gráfica 1 — RPS y Errores a lo largo del tiempo**

- Eje X: tiempo transcurrido
- Eje Y izquierdo: requests por segundo (línea azul)
- Eje Y derecho: errores por segundo (línea roja)
- Ventana deslizante de los últimos 5 minutos

**Gráfica 2 — Latencia a lo largo del tiempo**

- Eje X: tiempo transcurrido
- Tres líneas: P50 (verde), P95 (amarillo), P99 (rojo)
- Permite ver cuándo y cuánto se degrada la latencia

**Gráfica 3 — Workers activos**

- Muestra la curva de concurrencia a lo largo del test
- Especialmente útil en el escenario Ramp Up y Spike

**Gráfica 4 — Distribución de latencias (Histograma)**

- Barras estáticas que se actualizan cada 5 segundos
- Buckets: <50ms, 50-100ms, 100-250ms, 250-500ms, 500ms-1s, >1s

### Sección — Desglose por Endpoint

Tabla actualizada cada 5 segundos con una fila por endpoint:

| Endpoint | Requests | RPS | P50 | P95 | P99 | Errores | % Error |
|---|---|---|---|---|---|---|---|

Ordenable por cualquier columna. Permite identificar qué endpoint específico es el cuello de botella.

### Sección — Log de Errores Recientes

Lista de los últimos 20 errores, mostrando:

- Timestamp
- Endpoint
- Código HTTP (o tipo de error: timeout, connection error)
- Worker ID
- Mensaje de error si está disponible

Se actualiza en tiempo real vía HTMX polling cada 2 segundos.

---

## Endpoint SSE (`/stream`)

Emite un evento cada segundo con el siguiente payload JSON:

```json
{
  "ts": 1234567890,
  "elapsed_s": 42,
  "workers_active": 75,
  "rps": 1240.5,
  "error_rate_pct": 2.3,
  "throughput_kbps": 890.2,
  "latency": {
    "p50": 45.2,
    "p95": 132.7,
    "p99": 287.4
  },
  "total_requests": 52080,
  "total_errors": 1197
}
```

El cliente HTMX escucha este stream y actualiza los elementos del DOM con los nuevos valores, mientras Chart.js añade los nuevos puntos a las gráficas.

---

## Endpoint de Reporte (`/report`)

Disponible al finalizar el test. Devuelve el reporte completo en el formato solicitado:

- `GET /report?format=json` → descarga `report_<timestamp>.json`
- `GET /report?format=csv` → descarga `report_<timestamp>.csv`

El CSV contiene una fila por segundo del test con todas las métricas, útil para importar a Excel o Google Sheets para análisis posterior.

---

## Consideraciones de Implementación

- El dashboard debe ser funcional con JavaScript mínimo: HTMX maneja las actualizaciones y Chart.js las gráficas. No se usa ningún framework JS adicional.
- El HTML es servido desde templates Jinja2 de FastAPI.
- La hoja de estilos es mínima, usando Tailwind CSS vía CDN para no añadir dependencias de build.
- El servidor del dashboard corre en un thread del sistema operativo separado del runner (que usa el event loop de asyncio), para no interferir con la generación de carga.
