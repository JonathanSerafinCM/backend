# Guía de Desarrollo Frontend para Ticketera IA + Blockchain MVP

Este documento proporciona una guía exhaustiva para un agente de IA encargado de desarrollar la aplicación frontend para el Producto Mínimo Viable (MVP) de la Ticketera IA + Blockchain. Detalla el propósito de la aplicación, las características clave, la pila tecnológica recomendada y los flujos de interacción detallados con la API del backend.

## 1. Visión General de la Aplicación

*   **Propósito:** Una plataforma de venta de entradas para eventos descentralizada que permite a los organizadores crear eventos y a los compradores adquirir entradas NFT. Incluye recomendaciones de eventos y análisis de ventas.
*   **Tipo:** Aplicación Web.
*   **Características Clave del MVP:**
    *   Autenticación de Usuarios (Registro, Inicio de Sesión).
    *   Perfiles de Usuario (Comprador, Organizador).
    *   Gestión de Eventos (CRUD para Organizadores).
    *   Compra de Entradas (Minteo de entradas NFT).
    *   Visualización de Entradas del Usuario.
    *   Historial de Entradas (Trazabilidad en la blockchain).
    *   Recomendaciones de Eventos (Basadas en categorías).
    *   Análisis de Ventas (para Organizadores).

## 2. Pila Tecnológica Recomendada

*   **Framework Frontend:** Next.js (React) - Ofrece renderizado del lado del servidor (SSR) y generación de sitios estáticos (SSG), ideal para rendimiento y SEO.
*   **Estilado:** Tailwind CSS o Bootstrap - Para un desarrollo rápido y un diseño moderno y responsivo.
*   **Gestión de Estado:** React Context API o una librería ligera como Zustand/Jotai - Suficiente para la complejidad del MVP.
*   **Integración Web3:** Ethers.js o Web3.js - Para la conexión con billeteras (ej. MetaMask) y la interacción directa con la blockchain si fuera necesario (aunque la mayoría de las interacciones con el contrato se realizan a través del backend).
*   **Cliente API:** Axios o la API nativa `fetch` - Para realizar solicitudes HTTP al backend.

## 3. Endpoints de la API del Backend (Referencia)

La API del backend se ejecuta en `http://localhost:8000` (o la URL de despliegue). Todos los endpoints protegidos requieren un token JWT en el encabezado `Authorization: Bearer <token>`.

### 3.1. Autenticación y Usuarios

*   `POST /auth/register`
    *   **Descripción:** Registra un nuevo usuario.
    *   **Request Body:**
        ```json
        {
            "email": "string",
            "password": "string",
            "wallet_address": "string | null"
        }
        ```
    *   **Response:** `UserOut` object (id, email, role, wallet_address).
*   `POST /auth/login`
    *   **Descripción:** Autentica un usuario y devuelve un token JWT.
    *   **Request Body (form-data):**
        ```
        username: string (email)
        password: string
        ```
    *   **Response:**
        ```json
        {
            "access_token": "string",
            "token_type": "bearer"
        }
        ```
*   `GET /auth/users/me` (Protegido)
    *   **Descripción:** Obtiene la información del usuario autenticado.
    *   **Response:** `UserOut` object.

### 3.2. Gestión de Eventos

*   `POST /events` (Protegido, solo Organizador)
    *   **Descripción:** Crea un nuevo evento.
    *   **Request Body:**
        ```json
        {
            "name": "string",
            "description": "string | null",
            "date": "datetime (ISO 8601)",
            "location": "string",
            "price": "float",
            "total_tickets": "integer",
            "category": "string | null"
        }
        ```
    *   **Response:** `EventOut` object (id, name, description, date, location, price, total_tickets, category).
*   `GET /events`
    *   **Descripción:** Lista todos los eventos disponibles.
    *   **Response:** `list[EventOut]`
*   `GET /events/{event_id}`
    *   **Descripción:** Obtiene los detalles de un evento específico.
    *   **Response:** `EventOut` object.
*   `PUT /events/{event_id}` (Protegido, solo Organizador y dueño del evento)
    *   **Descripción:** Actualiza los detalles de un evento.
    *   **Request Body:** (Partial `EventCreate` object)
        ```json
        {
            "name": "string | null",
            "description": "string | null",
            "date": "datetime (ISO 8601) | null",
            "location": "string | null",
            "price": "float | null",
            "total_tickets": "integer | null",
            "category": "string | null"
        }
        ```
    *   **Response:** `EventOut` object.
*   `DELETE /events/{event_id}` (Protegido, solo Organizador y dueño del evento)
    *   **Descripción:** Elimina un evento.
    *   **Response:** `{"detail": "Event deleted successfully"}`

### 3.3. Interacción Blockchain

*   `POST /events/{event_id}/purchase` (Protegido, solo Comprador)
    *   **Descripción:** Compra y mintea un ticket NFT para un evento.
    *   **Response:**
        ```json
        {
            "message": "Ticket purchased and minted successfully",
            "transaction_hash": "string",
            "ticket_id": "integer"
        }
        ```
*   `GET /users/me/tickets` (Protegido)
    *   **Descripción:** Lista los tickets NFT propiedad del usuario autenticado.
    *   **Response:** `list[{"ticket_id": integer, "owner": string}]`
*   `GET /tickets/{ticket_id}/history`
    *   **Descripción:** Obtiene el historial de transferencias de un ticket NFT.
    *   **Response:**
        ```json
        {
            "ticket_id": "integer",
            "history": [
                {
                    "from": "string (address)",
                    "to": "string (address)",
                    "blockNumber": "integer",
                    "transactionHash": "string"
                }
            ]
        }
        ```
*   `GET /metadata/tickets/{ticket_id}`
    *   **Descripción:** Sirve los metadatos off-chain de un ticket NFT específico, siguiendo el estándar ERC721.
    *   **Response:**
        ```json
        {
            "name": "string",
            "description": "string",
            "image": "string (URL)",
            "attributes": [
                {"trait_type": "Event ID", "value": "integer"},
                {"trait_type": "Location", "value": "string"},
                {"trait_type": "Date", "value": "string (ISO 8601)"},
                {"trait_type": "Price", "value": "float"},
                {"trait_type": "Category", "value": "string"},
                {"trait_type": "Owner Wallet", "value": "string"}
            ]
        }
        ```

### 3.4. Módulo de IA

*   `GET /events/recommendations`
    *   **Descripción:** Obtiene recomendaciones de eventos. Puede filtrar por categoría si se proporciona `event_id`.
    *   **Query Parameters:** `event_id: integer | null`
    *   **Response:** `list[EventOut]`
*   `GET /admin/analytics/sales-by-category` (Protegido, solo Organizador)
    *   **Descripción:** Devuelve un análisis de ventas agrupado por categoría.
    *   **Response:**
        ```json
        [
            {"category": "string", "tickets_sold": "integer"},
            // ...
        ]
        ```

## 4. Flujos de Usuario Principales

### 4.1. Registro e Inicio de Sesión de Usuario

*   **Actores:** Comprador, Organizador.
*   **Flujo:**
    1.  **Página de Aterrizaje:** El usuario llega a la aplicación.
    2.  **Opción de Registro/Inicio de Sesión:** Se presenta al usuario la opción de registrarse o iniciar sesión.
    3.  **Registro (Comprador):**
        *   **Formulario:** Email, Contraseña, (Opcional) Dirección de Billetera (se puede integrar con MetaMask para obtenerla).
        *   **Llamada al Backend:** `POST /auth/register`.
        *   **Éxito:** Redirigir al Dashboard del Comprador / Lista de Eventos.
    4.  **Registro (Organizador):**
        *   **Formulario:** Email, Contraseña, (Opcional) Dirección de Billetera.
        *   *Nota:* Para el MVP, la asignación del rol de organizador se gestiona en el backend (ej. por un administrador). El frontend solo envía la solicitud de registro estándar.
        *   **Llamada al Backend:** `POST /auth/register`.
        *   **Éxito:** Redirigir al Dashboard del Organizador / Creación de Eventos.
    5.  **Inicio de Sesión:**
        *   **Formulario:** Email, Contraseña.
        *   **Llamada al Backend:** `POST /auth/login`.
        *   **Éxito:** Recibir el token JWT y almacenarlo de forma segura (ej. en `localStorage` o `HttpOnly cookie`). Redirigir al usuario según su rol (`/events` para comprador, `/organizer/events` para organizador).
    6.  **Perfil de Usuario (`/users/me`):**
        *   **Llamada al Backend:** `GET /auth/users/me` (con JWT).
        *   **Visualización:** Mostrar el email, rol y dirección de billetera del usuario.

### 4.2. Gestión de Eventos (Flujo del Organizador)

*   **Actores:** Organizador.
*   **Flujo:**
    1.  **Dashboard del Organizador:** El organizador inicia sesión y ve una opción para gestionar eventos.
    2.  **Crear Evento:**
        *   **Formulario:** Nombre, Descripción, Fecha, Ubicación, Precio, Total de Entradas, Categoría.
        *   **Llamada al Backend:** `POST /events` (con JWT).
        *   **Éxito:** Evento creado, redirigir a la lista de eventos.
    3.  **Ver Eventos:**
        *   **Llamada al Backend:** `GET /events` (se pueden filtrar por el organizador si es necesario, pero para el MVP, se listan todos los eventos).
        *   **Visualización:** Mostrar una lista de eventos, con opciones para Ver Detalles, Editar, Eliminar.
    4.  **Ver Detalles del Evento:**
        *   **Llamada al Backend:** `GET /events/{event_id}`.
        *   **Visualización:** Mostrar todos los detalles del evento.
    5.  **Editar Evento:**
        *   **Formulario:** Precargar con los datos existentes del evento. Permitir actualizaciones parciales.
        *   **Llamada al Backend:** `PUT /events/{event_id}` (con JWT).
        *   **Éxito:** Evento actualizado.
    6.  **Eliminar Evento:**
        *   **Diálogo de Confirmación.**
        *   **Llamada al Backend:** `DELETE /events/{event_id}` (con JWT).
        *   **Éxito:** Evento eliminado.

### 4.3. Compra de Entradas (Flujo del Comprador)

*   **Actores:** Comprador.
*   **Flujo:**
    1.  **Lista/Detalles de Eventos:** El comprador navega por los eventos.
    2.  **Seleccionar Evento:** El comprador selecciona un evento para ver los detalles.
    3.  **Comprar Entrada:**
        *   **Botón:** "Comprar Entrada".
        *   **Prerrequisito:** El usuario debe tener una dirección de billetera registrada (o se le debe pedir que la añada).
        *   **Llamada al Backend:** `POST /events/{event_id}/purchase` (con JWT).
        *   **Éxito:** Mostrar el hash de la transacción y el ID de la entrada. Actualizar la interfaz de usuario para reflejar la entrada comprada.

### 4.4. Visualización de Mis Entradas (Flujo del Comprador)

*   **Actores:** Comprador.
*   **Flujo:**
    1.  **Sección "Mis Entradas":** El comprador navega a una sección "Mis Entradas".
    2.  **Listar Entradas:**
        *   **Llamada al Backend:** `GET /auth/users/me/tickets` (con JWT).
        *   **Visualización:** Mostrar una lista de las entradas que posee (ID de la entrada, nombre del evento asociado).
    3.  **Ver Historial de Entradas:**
        *   Seleccionar una entrada de la lista.
        *   **Llamada al Backend:** `GET /tickets/{ticket_id}/history`.
        *   **Visualización:** Mostrar el historial de transferencias (de, a, número de bloque, hash de la transacción).

### 4.5. Recomendaciones de Eventos (Flujo General/Comprador)

*   **Actores:** Todos los usuarios (especialmente compradores).
*   **Flujo:**
    1.  **Sección de Recomendaciones:** Mostrar una sección para eventos recomendados (ej. en la página de inicio o en la lista de eventos).
    2.  **Obtener Recomendaciones:**
        *   **Llamada al Backend:** `GET /events/recommendations` (opcionalmente con `event_id` si se está viendo un evento específico).
        *   **Visualización:** Mostrar los eventos recomendados.

### 4.6. Análisis de Ventas (Flujo del Organizador)

*   **Actores:** Organizador.
*   **Flujo:**
    1.  **Dashboard del Organizador:** El organizador navega a una sección de "Análisis".
    2.  **Obtener Datos de Ventas:**
        *   **Llamada al Backend:** `GET /admin/analytics/sales-by-category` (con JWT).
        *   **Visualización:** Mostrar los datos de ventas, por ejemplo, como una tabla o un gráfico simple.

## 5. Consideraciones Generales para el Agente Frontend

*   **Manejo de Errores:** Implementar un manejo robusto de errores para todas las llamadas a la API. Mostrar mensajes amigables al usuario.
*   **Estados de Carga:** Mostrar indicadores de carga durante las llamadas a la API.
*   **Autenticación:** Almacenar y enviar de forma segura los tokens JWT con las solicitudes autenticadas. Manejar la expiración del token (ej. redirigir al inicio de sesión).
*   **Integración de Billetera (Opcional pero Recomendado):** Aunque el backend maneja el minteo, una billetera frontend (ej. MetaMask) podría usarse para la entrada de la `wallet_address` del usuario durante el registro/actualización del perfil, y potencialmente para mostrar la propiedad de NFT directamente desde la blockchain (aunque el backend también proporciona esto).
*   **Diseño Responsivo:** Asegurar que la aplicación sea utilizable en varios tamaños de pantalla.
*   **Experiencia de Usuario (UX):** Centrarse en una navegación intuitiva y una retroalimentación clara.
*   **Despliegue:** Proporcionar instrucciones claras para construir y desplegar la aplicación Next.js (ej. `npm run build`, `npm start`).
