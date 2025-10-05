# Ticketera IA + Blockchain – Backend MVP Context

> Última actualización: 4 de octubre de 2025  
> Repositorio: `backend` · Rama: `amoy`

Este documento resume el estado actual del MVP del backend "Ticketera IA + Blockchain" para que otro agente (humano o LLM) pueda entender rápidamente qué existe, cómo funciona y qué queda pendiente.

## Visión general 🧭

- **Propósito:** Plataforma de ticketing donde los organizadores crean eventos y los compradores adquieren tickets tokenizados como NFTs en Polygon (testnet Amoy). Incluye autenticación, CRUD de eventos, compra/mint de tickets, metadatos off-chain y analíticas básicas.
- **Stack principal:** FastAPI (Python 3.12) + SQLAlchemy/PostgreSQL + Web3.py para blockchain + contratos Solidity (ERC721).
- **Entrega actual:** Backend funcional con endpoints protegidos JWT, contrato ERC721 operativo, lógica de compra con minteo programático y simulación de pagos. Suite de tests automatizados para API, blockchain básico y analíticas.

## Componentes y arquitectura

- **Aplicación FastAPI (`main.py`)**: Expone routers para autenticación, usuarios, eventos, tickets (Web3), metadatos y endpoints administrativos. La app se inicia con CORS configurado desde `ALLOWED_ORIGINS`.
- **Base de datos:** PostgreSQL accesible vía `DATABASE_URL` (SQLAlchemy). Tablas generadas automáticamente en import usando `Base.metadata.create_all`.
- **Blockchain:** Contrato `TicketManager.sol` (ERC721, solo owner puede mintear) desplegado manualmente en Polygon Amoy. El backend firma transacciones con `PRIVATE_KEY` y opera sobre `CONTRACT_ADDRESS`.
- **Metadatos NFT:** Servidos desde `GET /metadata/tickets/{ticket_id}` basados en la información guardada en BD.
- **Infraestructura & tooling:** Dockerfile + docker-compose para backend + Postgres; scripts para compilar (`compile_contract.py`) y desplegar (`deploy_contract.py`, `deploy.py`) el contrato.

## Entorno y configuración

- **Dependencias Python:** Definidas en `requirements.txt` (FastAPI, SQLAlchemy, Web3, passlib, python-jose, etc.).
- **Variables de entorno críticas:**
  - `DATABASE_URL` (obligatoria, valida al arrancar).
  - `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` (seguridad JWT).
  - `ALLOWED_ORIGINS` (lista separada por comas para CORS, fallback seguro a dominio público).
  - `TESTNET_RPC_URL` (HTTP provider para Amoy o nodo local; default `http://127.0.0.1:8545`).
  - `CONTRACT_ADDRESS` (dirección `TicketManager` desplegado).
  - `PRIVATE_KEY` (clave con fondos para firmar mint; se deriva `ACCOUNT_ADDRESS` en import).

  *Nota:* `PRIVATE_KEY` debe pertenecer al owner del contrato; la app la lee en import y falla si falta.
- **Docker compose:** Levanta `ticketera-db` (Postgres 16) y `ticketera-backend` (Uvicorn) exponiendo `127.0.0.1:8010→8000`. Compose recalcula `DATABASE_URL` para el contenedor backend.
- **Requisitos para tests/blockchain:** Ganache/Anvil u otro RPC local en `http://127.0.0.1:8545` con cuentas prefundidas y misma `PRIVATE_KEY` usada en env. ABI (`TicketManager.abi`) y bytecode (`TicketManager.bin`) deben existir.

## Modelo de datos (`main.py`)

| Tabla | Campos clave | Notas |
|-------|---------------|-------|
| `users` | `id`, `email`, `hashed_password`, `wallet_address`, `role (comprador/organizador)` | `wallet_address` opcional; relación 1:N con `events`. |
| `events` | `id`, `name`, `description`, `date`, `location`, `price`, `total_tickets`, `category`, `total_revenue`, `is_funds_withdrawn`, `owner_id` | `total_revenue` suma simulada de ventas; `is_funds_withdrawn` soporta retiro simulado. |
| `tickets` | `id`, `ticket_id_onchain`, `event_id`, `owner_wallet_address`, `purchase_date`, `is_paid` | `ticket_id_onchain` se alinea con el `tokenId` ERC721. |

Las tablas se crean automáticamente al importar el módulo (no hay migraciones). Revisar posibles fixes si se piensa usar Alembic en producción.

## Superficie de API (backend actual)

### Autenticación & usuarios

- `POST /auth/register` · Crea usuario `COMPRADOR` por defecto (wallet opcional) y hashea contraseña.
- `POST /auth/login` · OAuth2 password flow, devuelve JWT (`access_token`, `token_type`).
- `GET /auth/users/me` · Devuelve perfil autenticado.
- `GET /users/me/tickets` · Lista tickets del wallet propio (consulta BD, no on-chain); requiere wallet registrada.
- `POST /admin/promote-to-organizer/{user_email}` · *Endpoint temporal* (sin auth) que eleva un usuario a `ORGANIZADOR`.

### Eventos

- `POST /events` · Solo organizadores; crea evento y lo asocia al usuario autenticado.
- `GET /events` · Lista todos los eventos.
- `GET /events/{id}` · Devuelve detalle.
- `PUT /events/{id}` · Solo organizador propietario; updates parciales (usa `EventUpdate`).
- `DELETE /events/{id}` · Solo organizador propietario.
- `POST /events/{id}/simulate-withdrawal` · Marca `is_funds_withdrawn=True` y devuelve monto recaudado.

### Compra de tickets & Web3

- `POST /events/{id}/purchase` · Solo compradores. Flujo: valida existencia y disponibilidad, requiere `wallet_address`. Construye `token_uri`, usa Web3 para `safeMint` con gas fijo (500k, 30 gwei, chainId 80002). Tras recibo → registra ticket en BD (`is_paid=True`, `purchase_date=utcnow`) y actualiza `total_revenue` y `total_tickets`.
- `GET /tickets/{ticket_id}/owner` · Consulta on-chain `ownerOf`.
- `GET /tickets/{ticket_id}/history` · Crea filtro de eventos `Transfer` desde bloque génesis.

### Metadatos & analíticas

- `GET /metadata/tickets/{ticket_id}` · Devuelve JSON estándar ERC721 (imagen placeholder + atributos event/ticket).
- `GET /events/recommendations` · Recomienda por categoría (si `event_id`, filtra mismo `category`; si no, retorna todos los eventos).
- `GET /admin/analytics/sales-by-category` · Solo organizadores; agrupa ventas por categoría vía join `Event`/`Ticket`.

## Flujos clave del MVP

1. **Registro/Login:** Usuario se registra (`wallet_address` opcional) → inicia sesión → recibe JWT para consumir endpoints protegidos.
2. **Promoción a organizador:** Temporalmente vía `/admin/promote-to-organizer/{email}` (sin auth, riesgo en prod).
3. **Gestión de eventos:** Organizadores crean/actualizan/elimnan eventos; cada operación impacta tabla `events`.
4. **Compra de ticket:** Comprador autenticado con wallet: al comprar, backend
   - Verifica `total_tickets` > 0.
   - Construye transacción `safeMint` usando `ACCOUNT_ADDRESS` (derivado de `PRIVATE_KEY`).
   - Espera recibo para extraer `tokenId` del evento `Transfer` (from `0x0`).
   - Persiste ticket en BD (simula pago) y descuenta inventario.
5. **Analíticas & retiro:** Organizadores pueden consultar ventas por categoría y marcar fondos retirados (simulado).
6. **Metadatos Off-chain:** Marketplace/billeteras consumen `GET /metadata/tickets/{id}` para mostrar NFT.

## Capa blockchain

- **Contrato `TicketManager.sol`:** Basado en OpenZeppelin (`ERC721`, `Ownable`, `Counters`). `safeMint` incrementa ID interno, mintea al destino y guarda URI. `tokenURI` reimplementado para devolver mapping `_tokenURIs`.
- **Scripts:**
  - `compile_contract.py` instala `solc 0.8.0`, compila usando `solcx` permitiendo imports desde `contracts/`, genera `TicketManager.abi/bin`.
  - `deploy_contract.py` despliega en red definida por `TESTNET_RPC_URL` (por defecto Amoy), gasta gas `2500000`, imprime dirección para copiar a `.env`.
  - `deploy.py` (local/Ganache): compila + despliega, actualiza `.env` con nueva `CONTRACT_ADDRESS`.
- **Dependencias de contrato:** Copias locales de librerías OpenZeppelin (`contracts/` dir) para compilación offline.

## Inteligencia artificial & analíticas

- **Recomendaciones:** Implementación básica (categoria). Tests lo tratan como placeholder pero endpoint responde datos reales.
- **Analíticas:** `sales-by-category` consulta real (agrupa tickets). No hay motor IA avanzado aún, pero datos (`total_revenue`, `tickets`, `category`) listos para evoluciones.

## Pruebas automatizadas (pytest)

- **Tests principales:** `test_auth.py`, `test_events.py`, `test_main.py`, `test_tickets.py`, `test_recommendations.py`, `test_analytics.py`, `test_contract.py`, etc. Usan `fastapi.testclient` y `SessionLocal` directo.
- **Configuración común:** `setup_database` limpia y recrea tablas; override de `get_w3` para apuntar a `http://127.0.0.1:8545` (requiere nodo activo).
- **Cobertura funcional:**
  - Autenticación/roles.
  - CRUD eventos + permisos.
  - Compra de tickets, historial, owner, listado del usuario.
  - Metadatos off-chain.
  - Analíticas por categoría.
  - Compilación/despliegue de contrato y `safeMint`.
- **Observaciones:**
  - `test_events.py` contiene un f-string mal cerrado (`f"Event with name {event_data["name"]}..."`) que impediría ejecutar pytest sin corregir comillas.
  - Varios tests (ej. `test_get_user_tickets`) llaman a `/auth/users/me/tickets`, pero la ruta real es `/users/me/tickets` (probable inconsistencia).
  - Ejecutar tests requiere BD accesible vía `DATABASE_URL` (no se setea automáticamente a SQLite). Se recomienda usar un PostgreSQL de pruebas.

## Scripts y utilidades adicionales

- `deploy.py` y `deploy_contract.py` cubren despliegues en local y Amoy respectivamente.
- Documentos de soporte (`FRONTEND_GUIDE.md`, `FRONTEND_INTEGRATION_UPDATES.md`, `MVP_*`, `DOCKER.md`) contienen alineación con frontend y justificaciones de arquitectura.
- `docker-compose.yml` facilita levantar stack en WSL/Windows; `Dockerfile` usa `python:3.12.6-slim` y ejecuta `uvicorn`.

## Limitaciones actuales

- **Dependencias en import:** La app falla al iniciar si faltan `DATABASE_URL`, `PRIVATE_KEY`, `TicketManager.abi`; conviene manejar estas validaciones con mejor mensajería/arranque diferido.
- **Seguridad:** Endpoint de promoción a organizador no requiere auth; ideal restringirlo antes de producción.
- **Simulación de pagos:** No hay cobro real; `total_revenue` e `is_paid` son banderas simuladas.
- **Escalabilidad DB:** Uso de `Base.metadata.create_all` en import no reemplaza migraciones. Para cambios futuros usar Alembic.
- **Pruebas:** Ajustar tests para rutas correctas y corregir sintaxis. Suite asume nodo blockchain local corriendo.
- **Metadatos NFT:** Imagen de ejemplo fija y atributos limitados; revisar antes de producción.

## Próximos pasos sugeridos

1. **Corregir y ejecutar suite de pruebas completa** (arreglar rutas/comillas, asegurar fixtures consistentes, considerar DB temporal SQLite para tests).
2. **Endurecer seguridad** (eliminar endpoint temporal o protegerlo, rotar claves en producción, manejar errores Web3).
3. **Automatizar despliegues** (scripts CI/CD, validación de contrato, seeds de datos).
4. **Extender IA** (popularidad basada en `tickets_sold`, personalización por historial usuario).
5. **Front-end & UX**: Repos front aún no iniciado según `GEMINI.md`; seguir guías en `FRONTEND_GUIDE.md`.
6. **Monitoreo**: Integrar observabilidad (sentry listo en requirements).

## Referencias útiles del repo

- `FRONTEND_GUIDE.md` y `FRONTEND_INTEGRATION_UPDATES.md` → contratos de interfaz con frontend.
- `MVP_APPROACH.md`, `MVP_*` → contexto de negocio y justificación técnica.
- `DOCKER.md` → guía paso a paso para levantar backend dockerizado.
- `TicketManager.sol` + `compile_contract.py` → contrato y pipeline de compilación.
- `test_*.py` → ejemplos de uso y expectativas funcionales.

---
Para cualquier ampliación, revise este archivo junto con los documentos MVP en la raíz y sincronice las variables de entorno antes de ejecutar la API.
