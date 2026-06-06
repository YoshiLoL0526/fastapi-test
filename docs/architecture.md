# Arquitectura General del Sistema

## Visión General

El proyecto consiste en dos sistemas independientes que corren en dos PCs distintas dentro de la misma red local (LAN). El objetivo es estresar una API de e-commerce con cargas realistas y observar su comportamiento mediante un dashboard en tiempo real.

---

## Componentes Principales

### 1. E-commerce API (`api/`)

Corre en la **PC servidor** (Intel Core i5-8250U, 12 GB RAM). Es una API REST completamente funcional que simula un sistema de comercio electrónico real. Expone endpoints HTTP/WebSocket para todos los dominios del negocio. No tiene conocimiento del load tester; simplemente recibe y responde peticiones.

Se levanta con **Gunicorn + Uvicorn workers** para aprovechar todos los núcleos disponibles del servidor.

### 2. Load Tester (`load_tester/`)

Corre en la **PC cliente** (AMD Ryzen 5 5500, 24 GB RAM). Tiene dos responsabilidades:

- **Runner**: genera tráfico hacia la API usando `httpx` en modo async con múltiples workers concurrentes. Simula usuarios reales ejecutando flujos completos (login → navegar → agregar al carrito → pagar).
- **Dashboard UI**: un servidor FastAPI liviano que sirve una interfaz web con HTMX y Chart.js, accesible desde cualquier PC en la LAN. Transmite métricas en tiempo real usando Server-Sent Events (SSE).

---

## Diagrama de Comunicación

```
[PC Cliente — Ryzen 5 5500 / 24 GB RAM]
┌──────────────────────────────────────────────┐
│                                              │
│   runner.py  ──────── HTTP requests ────────►│──────► [PC Servidor — i5-8250U / 12 GB RAM]
│      │        ◄───── HTTP responses ─────────│◄──────  api/ en :8000
│      │                                       │
│      ▼ (escribe métricas en memoria)         │
│   metrics store                              │
│      │                                       │
│      ▼ (lee métricas via SSE)                │
│   ui/main.py  :8001                          │
│                                              │
└──────────────────────────────────────────────┘
        ▲
        │  Browser (accesible desde ambas PCs)
```

---

## Principios de Diseño

- **Separación total**: la API no sabe que existe un tester. Esto garantiza que los resultados son puros.
- **Async de extremo a extremo**: tanto la API como el tester usan I/O asíncrono para maximizar la concurrencia.
- **Intercambiabilidad de BD**: la capa de base de datos está abstraída de forma que cambiar de SQLite a PostgreSQL es solo un cambio de variable de entorno y driver.
- **Escalabilidad horizontal**: la API está diseñada para correr con múltiples workers y en el futuro detrás de un load balancer.
- **Realismo**: los flujos del tester imitan comportamiento humano real, no peticiones aisladas a endpoints individuales.

---

## Puertos y Acceso en LAN

| Servicio | PC | Puerto | Acceso |
|---|---|---|---|
| E-commerce API | Servidor (i5) | `8000` | LAN + local |
| Dashboard UI | Cliente (Ryzen 5) | `8001` | LAN + local |

La URL base de la API se configura en el load tester mediante variable de entorno, lo que permite apuntar a cualquier host sin tocar el código.
