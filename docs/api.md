# E-commerce API — Requisitos Funcionales

## Descripción General

Una API REST de comercio electrónico que simula un sistema de producción real. Está construida con FastAPI y expone endpoints para todos los flujos típicos de un e-commerce: autenticación, catálogo de productos, carrito de compras, órdenes, pagos, inventario, reseñas y carga de archivos. Incluye además un canal WebSocket para notificaciones en tiempo real.

El criterio principal de diseño es el **realismo**: cada endpoint tiene la lógica de negocio, validaciones, relaciones entre entidades y patrones de acceso a base de datos que tendría en producción real, no versiones simplificadas.

---

## Dominio de Negocio

### Autenticación (`/auth`)

Gestiona el ciclo de vida de la sesión del usuario.

- **Registro**: crea un nuevo usuario con email, nombre y contraseña hasheada. Valida unicidad de email.
- **Login**: autentica con email y contraseña, devuelve un access token JWT y un refresh token.
- **Refresh**: genera un nuevo access token a partir de un refresh token válido, sin requerir contraseña.
- **Logout**: invalida el refresh token en base de datos.
- **Perfil propio**: devuelve los datos del usuario autenticado.

Los tokens JWT tienen expiración corta (access: 15 min, refresh: 7 días). Toda ruta protegida requiere el header `Authorization: Bearer <token>`.

---

### Usuarios (`/users`)

Gestión de cuentas de usuario, accesible solo para el propio usuario o administradores.

- **Ver perfil**: datos personales, dirección de envío por defecto, fecha de registro.
- **Actualizar perfil**: nombre, teléfono, dirección.
- **Cambiar contraseña**: requiere contraseña actual como verificación.
- **Historial de órdenes**: lista paginada de todas las órdenes del usuario.
- **Listar usuarios** *(solo admin)*: listado paginado con filtros por estado y fecha de registro.

---

### Productos (`/products`)

El catálogo es la parte más consultada de cualquier e-commerce. Incluye búsqueda, filtrado y paginación eficientes.

- **Listar productos**: paginación con cursor, filtros por categoría, rango de precio, disponibilidad y rating mínimo. Ordenamiento por precio, rating, fecha de creación o popularidad.
- **Buscar productos**: búsqueda por texto en nombre y descripción.
- **Detalle de producto**: información completa incluyendo stock actual, rating promedio y últimas reseñas.
- **Crear producto** *(solo admin)*: nombre, descripción, precio, categoría, stock inicial e imagen.
- **Actualizar producto** *(solo admin)*: edición parcial de cualquier campo.
- **Eliminar producto** *(solo admin)*: baja lógica (no elimina de BD).
- **Productos relacionados**: devuelve productos de la misma categoría con buen rating.

---

### Categorías (`/categories`)

Estructura jerárquica para organizar el catálogo.

- **Listar categorías**: árbol completo de categorías con conteo de productos por categoría.
- **Detalle de categoría**: nombre, descripción y productos que la componen.
- **CRUD completo** *(solo admin)*: crear, editar y eliminar categorías.

---

### Carrito (`/cart`)

El carrito es temporal y está asociado a la sesión del usuario autenticado. Opera principalmente en memoria de la sesión pero persiste en BD para recuperación.

- **Ver carrito**: contenido actual con precios actualizados, subtotal, impuestos y total.
- **Agregar ítem**: valida que el producto existe y tiene stock suficiente. Si el ítem ya está en el carrito, incrementa la cantidad.
- **Actualizar cantidad**: cambia la cantidad de un ítem. Si la cantidad es 0, lo elimina.
- **Eliminar ítem**: quita un producto específico del carrito.
- **Vaciar carrito**: elimina todos los ítems.
- **Aplicar cupón**: valida un código de descuento y lo aplica al carrito.

Cada operación de escritura en el carrito recalcula el total considerando precios actuales (no los del momento en que se agregó el ítem).

---

### Órdenes (`/orders`)

El flujo de órdenes es el más complejo del sistema e involucra múltiples entidades y side effects.

- **Crear orden (checkout)**: convierte el carrito actual en una orden. Valida stock de todos los ítems, reserva el stock, calcula totales, crea el registro de pago pendiente y dispara una background task para el procesamiento.
- **Ver orden**: detalle completo de una orden con ítems, precios, estado del pago y estado de envío.
- **Historial de órdenes**: lista paginada de órdenes del usuario con filtros por estado y fecha.
- **Cancelar orden**: solo si está en estado pendiente. Libera el stock reservado.
- **Listar todas las órdenes** *(solo admin)*: con filtros por estado, usuario y rango de fechas.
- **Actualizar estado** *(solo admin)*: transiciona la orden entre estados (pendiente → procesando → enviado → entregado).

Estados posibles de una orden: `pending`, `processing`, `shipped`, `delivered`, `cancelled`, `refunded`.

---

### Pagos (`/payments`)

Simula la integración con una pasarela de pago externa. Incluye delays artificiales para representar la latencia real de llamadas a terceros.

- **Procesar pago**: recibe el ID de la orden y los datos de pago (tarjeta simulada). Introduce un delay de entre 300ms y 800ms para simular la llamada a la pasarela. Tiene una tasa de fallo configurable (por defecto 5%) para simular rechazos reales.
- **Estado del pago**: consulta el estado actual de un pago.
- **Reembolso**: inicia un reembolso para una orden entregada. También tiene delay artificial.
- **Historial de pagos del usuario**: todos los intentos de pago del usuario.

---

### Inventario (`/inventory`)

Gestión del stock de productos. Tiene implicaciones de consistencia importantes bajo concurrencia.

- **Ver stock de un producto**: cantidad disponible, cantidad reservada y cantidad total.
- **Ajustar stock** *(solo admin)*: incrementa o decrementa el stock disponible de un producto. Registra el motivo del ajuste.
- **Reporte de stock bajo** *(solo admin)*: lista de productos cuyo stock está por debajo de un umbral configurable.
- **Historial de movimientos**: log de todos los cambios de stock de un producto (reservas, liberaciones, ajustes manuales).

Las operaciones de reserva y liberación de stock son atómicas para evitar condiciones de carrera bajo alta concurrencia.

---

### Reseñas (`/reviews`)

Sistema de valoraciones de productos por parte de compradores verificados.

- **Listar reseñas de un producto**: paginadas, ordenadas por fecha o por utilidad.
- **Crear reseña**: solo usuarios que hayan comprado el producto pueden reseñarlo. Incluye puntuación (1-5) y comentario de texto.
- **Actualizar reseña**: el autor puede editar su propia reseña.
- **Eliminar reseña**: el autor o un administrador puede eliminarla.
- **Marcar como útil**: los usuarios pueden votar si una reseña les fue útil.
- **Rating promedio**: se recalcula automáticamente al crear, editar o eliminar una reseña mediante una background task.

---

### Carga de Archivos (`/uploads`)

Manejo de imágenes para productos.

- **Subir imagen de producto**: acepta archivos JPEG/PNG/WebP con un límite de tamaño. Valida el tipo real del archivo (no solo la extensión). Guarda el archivo en disco con nombre único y devuelve la URL.
- **Eliminar imagen** *(solo admin)*: elimina la imagen del disco y su referencia en BD.

---

### WebSockets (`/ws`)

Canal de comunicación bidireccional en tiempo real.

- **Estado de orden en tiempo real**: el cliente se suscribe a un canal por `order_id`. El servidor empuja actualizaciones cuando el estado de la orden cambia (disparado por el proceso de pago y las actualizaciones de admin).
- **Alertas de stock**: canal para administradores que notifica cuando un producto cae por debajo del umbral de stock mínimo.

---

### Health y Métricas Internas (`/health`)

Endpoints de observabilidad propios del servidor.

- **Health check**: devuelve el estado del servidor, la conexión a base de datos y el tiempo de respuesta de cada subsistema.
- **Métricas internas** *(solo admin)*: requests activos, conexiones a BD, uso de memoria del proceso, tiempo de uptime.

---

## Patrones Transversales

### Middleware

- **Request ID**: cada request recibe un ID único (UUID) que se incluye en la respuesta y en los logs.
- **Timing**: el middleware mide el tiempo total de procesamiento de cada request y lo agrega al header de respuesta (`X-Process-Time`).
- **Rate limiting básico**: límite por IP para prevenir abuso extremo (configurable, desactivable para los tests).

### Background Tasks

Las siguientes operaciones se procesan de forma asíncrona para no bloquear la respuesta:

- Envío de email de confirmación de orden.
- Recálculo del rating promedio de un producto tras una nueva reseña.
- Actualización del contador de popularidad de un producto.
- Notificación de stock bajo a administradores.

### Roles y Autorización

Solo existen dos roles: `user` y `admin`. El rol se incluye en el payload del JWT. Los endpoints de administración validan el rol mediante una dependencia de FastAPI reutilizable.

### Paginación

Todos los endpoints de listado usan paginación basada en offset/limit con un máximo de 100 ítems por página. La respuesta siempre incluye el total de registros, la página actual y si existe una página siguiente.
