# Documentación Técnica y Arquitectura - MyWishList

## 1. Visión General del Proyecto
**MyWishList** es una aplicación web diseñada para centralizar enlaces de artículos de distintas tiendas en línea en una única lista de deseos personal y compartible. 

### Reglas de Negocio Principales
1. **Lectura Pública:** Cualquier persona (sin necesidad de iniciar sesión) puede visualizar la wishlist de cualquier usuario mediante su enlace o buscador (`?user=username`).
2. **Escritura Protegida (Autoría):** Solo un usuario autenticado puede crear artículos en su propia lista, y únicamente el autor original de un artículo puede editarlo o eliminarlo.
3. **Campos del Artículo:**
   - **Título** (Obligatorio)
   - **Precio** (Obligatorio, numérico `>= 0`)
   - **Descripción** (Opcional)
   - **Link del artículo (`url`)** (Obligatorio, validado como URL HTTP/HTTPS)
   - **Link de imagen (`image_url`)** (Obligatorio/con fallback visual en frontend)

---

## 2. Arquitectura del Sistema

El proyecto implementa una arquitectura **Cliente-Servidor desacoplada** (API RESTful + Frontend Estático SPA-like con Vanilla JS).

### 2.1 Stack Tecnológico
- **Backend:** Python 3.14+, FastAPI, SQLAlchemy (ORM), Pydantic (Validación).
- **Base de Datos:** SQLite (archivo local `wishlist.db`).
- **Seguridad:** `pwdlib` / `bcrypt` (Hashing de contraseñas), `PyJWT` (JSON Web Tokens).
- **Frontend:** HTML5 semántico, CSS3 moderno (Custom Properties, Flexbox, CSS Grid), Vanilla JavaScript (`fetch` API, ES6 Modules).

### 2.2 Estructura de Directorios (Arquitectura en Capas)

```text
MyWhishList/
├── backend/
│   ├── __init__.py
│   ├── main.py              # Punto de entrada FastAPI, montaje de estáticos y routers
│   ├── config.py            # Variables de entorno y configuración global (pydantic-settings)
│   ├── database.py          # Configuración de SQLAlchemy (Engine, SessionLocal, Base)
│   ├── dependencies.py      # Inyección de dependencias (get_db, get_current_user)
│   ├── models.py            # Modelos ORM de Base de Datos (User, WishlistItem)
│   ├── schemas.py           # Esquemas Pydantic (DTOs de entrada y salida)
│   ├── security.py          # Hashing de contraseñas y firma/validación de JWT
│   ├── services/            # Capa de lógica de negocio y acceso a datos
│   │   ├── __init__.py
│   │   ├── auth_service.py  # Creación y verificación de usuarios
│   │   └── item_service.py  # Operaciones CRUD y verificación de propiedad (ownership)
│   └── routers/             # Capa de controladores HTTP (Endpoints)
│       ├── __init__.py
│       ├── auth.py          # /api/auth (register, login, me)
│       ├── wishlists.py     # /api/wishlists (lectura pública de listas y usuarios)
│       └── items.py         # /api/items (escritura protegida: POST, PUT, DELETE)
│
├── frontend/
│   ├── index.html           # Vista principal (Modo Visitante y Modo Autor)
│   ├── login.html           # Vista de Inicio de Sesión y Registro
│   ├── css/
│   │   └── styles.css       # Estilos globales, variables, diseño responsive
│   └── js/
│       ├── api.js           # Cliente HTTP (wrapper sobre fetch, manejo de JWT y errores)
│       ├── auth.js          # Lógica de formulario de login/registro y sesión
│       └── app.js           # Renderizado del DOM, eventos y control de vistas
│
├── docs/
│   └── ARCHITECTURE.md      # Este documento
├── tests/                   # Pruebas automatizadas con pytest
├── .env.example             # Plantilla de variables de entorno
├── .gitignore
└── requirements.txt
```

---

## 3. Patrones de Diseño a Implementar

1. **Arquitectura en Capas (Layered Architecture):**
   - **Capa de Presentación / Controladores (`routers/`):** Solo maneja peticiones HTTP, códigos de estado y delega el trabajo a los servicios.
   - **Capa de Negocio / Servicios (`services/`):** Contiene las reglas de negocio (ej. verificar si el usuario que intenta borrar un ítem es realmente el dueño) y realiza las consultas a la base de datos.
   - **Capa de Acceso a Datos (`models.py` + `database.py`):** Define la estructura física de las tablas y gestiona las transacciones de SQLAlchemy.
2. **DTO (Data Transfer Object) con Pydantic (`schemas.py`):**
   - Desacopla los modelos internos de la base de datos de los datos expuestos en la API. Garantiza que campos sensibles como `hashed_password` jamás salgan en una respuesta JSON.
3. **Inyección de Dependencias (Dependency Injection - `dependencies.py`):**
   - Uso nativo de `Depends()` de FastAPI para proveer sesiones de base de datos por petición (`get_db`) y extraer/validar al usuario autenticado (`get_current_user`).
4. **API Client Wrapper en Frontend (`frontend/js/api.js`):**
   - Centraliza todas las llamadas `fetch` en una única función/módulo que adjunta automáticamente la cabecera `Authorization: Bearer <token>`, serializa el JSON y maneja errores globales.

---

## 4. Modelo de Datos y Esquema de Base de Datos

### Tabla: `users`
| Columna | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY, AUTOINCREMENT` | Identificador único |
| `username` | `VARCHAR(30)` | `UNIQUE, NOT NULL, INDEX` | Nombre de usuario normalizado para URL |
| `hashed_password` | `VARCHAR(255)` | `NOT NULL` | Hash bcrypt/argon2 de la contraseña |
| `created_at` | `DATETIME` | `DEFAULT CURRENT_TIMESTAMP` | Fecha de registro |

### Tabla: `wishlist_items`
| Columna | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY, AUTOINCREMENT` | Identificador único del artículo |
| `title` | `VARCHAR(150)` | `NOT NULL` | Nombre o título del producto |
| `price` | `NUMERIC(10, 2)` | `NOT NULL, CHECK(price >= 0)` | Precio del artículo |
| `description` | `TEXT` | `NULLABLE` | Notas o detalles opcionales |
| `url` | `VARCHAR(2048)` | `NOT NULL` | Enlace a la tienda en línea |
| `image_url` | `VARCHAR(2048)` | `NOT NULL` | Enlace a la imagen del producto |
| `user_id` | `INTEGER` | `FOREIGN KEY (users.id) ON DELETE CASCADE` | Autor/dueño del artículo |
| `created_at` | `DATETIME` | `DEFAULT CURRENT_TIMESTAMP` | Fecha de creación |

---

## 5. Flujo de Datos y Contrato de la API

### 5.1 Flujo de Lectura Pública (Cualquier Visitante)
```text
[Navegador Visitante] 
   │  1. Entra a /?user=alex
   ▼
[app.js] ── 2. GET /api/wishlists/alex (Sin Token) ──► [Router: wishlists.py]
                                                               │
                                                               ▼
[app.js] ◄── 3. JSON { username, items: [...] } ────── [SQLite: SELECT items]
   │
   ▼
4. Renderiza tarjetas en modo lectura (sin botones Editar/Borrar)
```

### 5.2 Flujo de Escritura Protegida (Autor Logueado)
```text
[Navegador Autor]
   │  1. Envía formulario "Nuevo Artículo"
   ▼
[app.js] ── 2. POST /api/items (Header: Bearer JWT) ──► [Dependency: get_current_user]
                                                               │ (Valida firma JWT y extrae user)
                                                               ▼
                                                        [Schema: ItemCreate]
                                                               │ (Valida URLs, precio >= 0)
                                                               ▼
[app.js] ◄── 3. HTTP 201 Created (ItemResponse JSON) ── [Service: Crea item con user.id]
   │
   ▼
4. Agrega tarjeta al DOM con botones "Editar" y "Eliminar"
```

### 5.3 Resumen de Endpoints

| Método | Endpoint | Acceso | Descripción | Códigos HTTP |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Público | Registra un nuevo usuario | `201`, `400`, `422` |
| `POST` | `/api/auth/login` | Público | Autentica y devuelve Token JWT | `200`, `401` |
| `GET` | `/api/auth/me` | **Protegido** | Devuelve datos del usuario logueado | `200`, `401` |
| `GET` | `/api/wishlists` | Público | Lista usuarios con wishlists públicas | `200` |
| `GET` | `/api/wishlists/{username}` | Público | Obtiene la wishlist completa de `{username}` | `200`, `404` |
| `POST` | `/api/items` | **Protegido** | Crea un artículo en la lista del usuario actual | `201`, `401`, `422` |
| `PUT` | `/api/items/{item_id}` | **Protegido (Autor)** | Edita un artículo si pertenece al usuario actual | `200`, `401`, `403`, `404` |
| `DELETE` | `/api/items/{item_id}` | **Protegido (Autor)** | Elimina un artículo si pertenece al usuario actual | `204`, `401`, `403`, `404` |

---

## 6. Reglas de Seguridad y Edge Cases

1. **Prevención de IDOR (Insecure Direct Object Reference):**
   - Nunca confiar en que ocultar los botones en el frontend protege la aplicación.
   - En `PUT /api/items/{id}` y `DELETE /api/items/{id}`, el backend debe verificar explícitamente:
     - Si el artículo no existe -> `404 Not Found`.
     - Si `item.user_id != current_user.id` -> `403 Forbidden`.
2. **Prevención de XSS (Cross-Site Scripting):**
   - **En Backend:** Validar que `url` e `image_url` utilicen exclusivamente esquemas `http://` o `https://` mediante `HttpUrl` de Pydantic (bloqueando vectores como `javascript:alert(1)`).
   - **En Frontend:** Prohibido concatenar datos del usuario dentro de `.innerHTML`. Se debe construir el DOM con `document.createElement()` y asignar textos mediante `.textContent`.
   - En los enlaces `<a href="...">`, incluir siempre `target="_blank" rel="noopener noreferrer"`.
3. **Seguridad de Contraseñas y JWT:**
   - Contraseñas hasheadas con algoritmo `bcrypt` (nunca texto plano).
   - Secretos (`SECRET_KEY`) cargados desde `.env`, nunca expuestos en el código fuente.
   - Tokens JWT con tiempo de expiración definido (`exp`, ej. 24 horas).
4. **Normalización de `username`:**
   - Validación por expresión regular `^[a-zA-Z0-9_-]{3,30}$` y conversión a minúsculas para garantizar URLs limpias y compartibles (`?user=username`).
5. **Manejo de Imágenes Rotos (Broken Links) y Precios:**
   - Los elementos `<img>` tendrán un manejador `onerror` para cargar un SVG/imagen *placeholder* local si la tienda externa bloquea la imagen o el link caduca.
   - Los precios se almacenan como `Numeric(10, 2)` / `Decimal` en Python para evitar errores de precisión de punto flotante (`float`).

---

## 7. Estándares de Formato y Código Limpio

### Python (Backend)
- **Guía de Estilo:** PEP 8.
- **Type Hints Obligatorios:** Todas las funciones y métodos deben declarar tipos de argumentos y retorno (`def create_item(db: Session, item: ItemCreate, user_id: int) -> WishlistItem:`).
- **Nombres:**
  - `snake_case` para variables, funciones y módulos.
  - `PascalCase` para clases (Modelos SQLAlchemy y Esquemas Pydantic).
  - `UPPER_SNAKE_CASE` para constantes de configuración.
- **Funciones Pequeñas y de Responsabilidad Única (SRP):** Un endpoint no debe escribir consultas SQL complejas directamente; debe llamar a una función del módulo `services/`.

### HTML, CSS y JavaScript (Frontend)
- **HTML5 Semántico:** Uso de `<header>`, `<main>`, `<section>`, `<article>`, `<form>`, `<dialog>` o modales accesibles.
- **CSS:**
  - Uso de variables CSS (`:root { --primary-color: ... }`) para mantener consistencia visual.
  - Nomenclatura de clases clara (estilo BEM simplificado o descriptivo: `.item-card`, `.item-card__title`, `.btn--primary`).
- **JavaScript:**
  - Uso de `const` y `let` (nunca `var`), `async / await` para promesas, y módulos ES6 (`import` / `export`).
  - Separación entre lógica de red (`api.js`), autenticación (`auth.js`) y manipulación del DOM (`app.js`).

---

## 8. Hoja de Ruta (Roadmap con Checklist)

### Fase 1: Configuración Inicial y Base de Datos
- [x] Crear estructura de carpetas (`backend/`, `frontend/`, `tests/`).
- [x] Configurar archivo `requirements.txt`, `.gitignore` y `.env.example`.
- [ ] Implementar `backend/config.py` y `backend/database.py` (conexión SQLite).
- [ ] Definir modelos `User` y `WishlistItem` en `backend/models.py`.
- [ ] Definir esquemas de validación Pydantic en `backend/schemas.py`.

### Fase 2: Seguridad y Autenticación (Backend)
- [ ] Implementar hashing de contraseñas y funciones JWT en `backend/security.py`.
- [ ] Implementar dependencia `get_current_user` en `backend/dependencies.py`.
- [ ] Crear servicio `backend/services/auth_service.py`.
- [ ] Crear endpoints `/api/auth/register`, `/api/auth/login` y `/api/auth/me` en `backend/routers/auth.py`.

### Fase 3: Lógica de Wishlists e Items (Backend)
- [ ] Crear servicio `backend/services/item_service.py` (CRUD + validación de propietario).
- [ ] Crear endpoints públicos `GET /api/wishlists` y `GET /api/wishlists/{username}` en `backend/routers/wishlists.py`.
- [ ] Crear endpoints protegidos `POST`, `PUT`, `DELETE` en `backend/routers/items.py`.
- [ ] Integrar routers y servir archivos estáticos del frontend en `backend/main.py`.

### Fase 4: Frontend - Estilos Base y Autenticación
- [ ] Diseñar sistema de estilos en `frontend/css/styles.css` (Grid de tarjetas, formularios, navbar, responsive).
- [ ] Implementar cliente `fetch` centralizado en `frontend/js/api.js`.
- [ ] Construir `frontend/login.html` y su lógica en `frontend/js/auth.js` (login, registro, guardado de token).

### Fase 5: Frontend - Wishlist Pública y Panel de Autor
- [ ] Construir estructura principal en `frontend/index.html` (barra de navegación, buscador de usuarios, contenedor de tarjetas, formulario/modal de artículo).
- [ ] Implementar renderizado seguro de tarjetas (`textContent`, fallback de imágenes) en `frontend/js/app.js`.
- [ ] Implementar detección de modo Visitante vs. modo Autor (mostrar/ocultar controles de creación, edición y borrado según usuario logueado).
- [ ] Implementar botón "Compartir Wishlist" (copiar URL `?user=username` al portapapeles).

### Fase 6: Pruebas y Pulido Final
- [ ] Verificar casos borde (URLs inválidas, intento de borrar ítem ajeno -> `403`, usuario no encontrado -> `404`, imágenes rotas).
- [ ] Escribir pruebas de integración básicas en `tests/` y documentar instrucciones de ejecución en `README.md`.
