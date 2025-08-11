# Arquitectura y Flujo del MVP - Ticketera IA + Blockchain

Este documento explica cómo se ha implementado el Producto Mínimo Viable (MVP) de la Ticketera, justificando las decisiones técnicas tomadas y cómo cumplen con los requisitos definidos. Se detalla el flujo actual de la aplicación y se explica por qué este enfoque es adecuado para un MVP, dejando una base sólida para futuras expansiones.

## 1. Cumplimiento de los Requisitos del MVP

La implementación actual del backend cumple con todos los puntos esenciales definidos en `requisitos.md`, tanto en la gestión tradicional como en los módulos de Blockchain e IA.

### I. Core del Backend y API (Fundamentos)

- **Autenticación y Usuarios:**
  - Se han implementado los endpoints `POST /auth/register`, `POST /auth/login` y `GET /auth/users/me`.
  - Se utiliza un sistema de roles (`COMPRADOR`, `ORGANIZADOR`) para controlar el acceso a ciertas funcionalidades.
- **Gestión de Eventos (CRUD para Organizadores):**
  - Se han implementado todos los endpoints requeridos: `POST /events`, `GET /events`, `GET /events/{event_id}`, `PUT /events/{event_id}`, `DELETE /events/{event_id}`.
  - Los datos de los eventos se almacenan en una base de datos relacional (PostgreSQL) como se especificó.

### II. Módulo Blockchain (Trazabilidad del Ticket)

- **Smart Contract (Ticket como NFT - Estándar ERC721):**
  - El contrato `TicketManager.sol` sigue el estándar ERC721.
  - Se han implementado funciones esenciales como `safeMint`, `ownerOf` y `tokenURI`.
  - Se ha añadido funcionalidad para registrar una URI de metadatos para cada ticket.
- **API Endpoints para la Interacción Blockchain:**
  - `POST /events/{event_id}/purchase`: Verifica disponibilidad, mitea un NFT en la blockchain a la billetera del comprador y actualiza la base de datos.
  - `GET /users/me/tickets`: Consulta los NFTs propiedad del usuario en la blockchain.
  - `GET /tickets/{ticket_id}/history`: Obtiene el historial de transferencias de un ticket desde la blockchain.
- **Metadatos del Ticket (Off-Chain):**
  - `GET /metadata/tickets/{ticket_id}`: Sirve los metadatos JSON para un ticket específico, tal como lo requiere el estándar ERC721.

### III. Módulo de IA (Recomendaciones y Análisis)

- **Recomendaciones de Eventos:**
  - `GET /events/recommendations`: Implementa una lógica simple de recomendación basada en la categoría del evento, cumpliendo con el requisito MVP.
- **Análisis de Demanda (Para el Organizador):**
  - `GET /admin/analytics/sales-by-category`: Proporciona datos de análisis agrupados por categoría, tal como se solicitó.

## 2. Flujo Actual de la Aplicación

1.  **Autenticación:** Un usuario se registra o inicia sesión. Si es un comprador, puede registrar su dirección de billetera.
2.  **Gestión de Eventos:** Un organizador crea eventos, que se almacenan en la base de datos del backend.
3.  **Compra de Tickets:**
    *   Un comprador selecciona un evento.
    *   El backend verifica la disponibilidad en su base de datos.
    *   El backend firma y envía una transacción al contrato inteligente `TicketManager` para mintear un nuevo NFT.
    *   El NFT se asigna a la dirección de billetera del comprador (`wallet_address`).
    *   El backend actualiza la disponibilidad del evento en su base de datos.
    *   Se devuelve al frontend el hash de la transacción y el ID del ticket (tokenId del NFT).
4.  **Visualización y Trazabilidad:**
    *   El comprador puede ver sus tickets (`GET /users/me/tickets`) consultando directamente al contrato.
    *   Se puede ver el historial de un ticket (`GET /tickets/{ticket_id}/history`).
    *   Los metadatos del ticket se sirven desde un endpoint off-chain (`GET /metadata/tickets/{ticket_id}`).
5.  **Inteligencia:**
    *   Se ofrecen recomendaciones de eventos basadas en categorías.
    *   Los organizadores pueden ver análisis de ventas simples.

## 3. Justificación del Enfoque Actual como MVP

El flujo y arquitectura actuales están diseñados específicamente para un MVP funcional y demostrable, y se justifican por las siguientes razones:

### a. **Enfoque en la Demostración de la Integración con la Blockchain**

- **Objetivo Principal:** Probar y demostrar la capacidad de la aplicación para interactuar con una blockchain, mintear NFTs y verificar su propiedad mediante llamadas a un contrato inteligente.
- **Logro:** El MVP demuestra claramente este flujo: crear evento (off-chain) -> comprar ticket (mint en blockchain) -> verificar ticket (consulta on-chain). Este es el núcleo de la propuesta de valor de una ticketera basada en blockchain.

### b. **Simplificación del Flujo de Usuario y Desarrollo**

- **Experiencia de Compra Simplificada:** Al no requerir que el comprador firme una transacción de pago compleja en su billetera para cada compra, se facilita enormemente la experiencia de usuario para demostraciones y pruebas iniciales.
- **Control del Backend:** El backend firma la transacción de minteo, lo cual permite:
  - Implementar fácilmente lógica de validación compleja antes de la emisión del ticket.
  - Simular fácilmente un sistema de pago (por ejemplo, cobro con tarjeta de crédito fuera de la blockchain) y luego emitir el NFT como comprobante.
  - Tener un proceso de desarrollo y prueba más directo para el equipo frontend.

### c. **Separación de Preocupaciones y Arquitectura Híbrida**

- **Backend como "Emisor de Tickets" (Issuer):** El backend actúa como una entidad autorizada que emite NFTs. Este es un modelo válido y común en muchas plataformas de tickets digitales.
- **Lógica de Negocio vs. Registro Inmutable:** La lógica de negocio (precios, disponibilidad, promociones) reside en el backend, mientras que la blockchain se encarga del registro inmutable de la propiedad. Esta separación clara es beneficiosa para el mantenimiento y la evolución.
- **Base para Futuras Expansión:** Este diseño permite evolucionar fácilmente hacia modelos más descentralizados (pagos on-chain) o mantener un modelo híbrido (pagos off-chain, propiedad on-chain).

### d. **Cumplimiento de Requisitos sin Complejidad Innecesaria**

- **Cumple con `requisitos.md`:** Todos los puntos esenciales están cubiertos.
- **Simulación de Pago:** El requisito de "(Simula el pago por ahora)" para el endpoint de compra se ha implementado explícitamente. Se ha añadido `is_paid`, `purchase_date` y `total_revenue` para dejar constancia de esta simulación.
- **Futuras Expansión:** Se ha añadido un endpoint `POST /events/{event_id}/simulate-withdrawal` para simular el ciclo completo de negocio, cumpliendo con el espíritu del MVP sin añadir la complejidad técnica del cobro directo.

## 4. Base Sólida para Futuras Expansiones

Esta implementación del MVP proporciona una base extremadamente sólida para cualquier evolución futura:

- **Conexión con la Blockchain Establecida:** La aplicación ya tiene la capacidad de conectarse a una red (Polygon Amoy), interactuar con un contrato y ejecutar transacciones. Esta infraestructura está completamente funcional.
- **Contrato ERC721 Funcional:** El contrato `TicketManager.sol` es un punto de partida válido. Para migrar a un modelo de pago on-chain, solo se necesitaría actualizar este contrato (por ejemplo, añadiendo `buyAndMint` con `msg.value`) y modificar ligeramente la lógica de llamada en el backend o frontend.
- **Arquitectura Modular:** Los módulos de autenticación, gestión de eventos, blockchain e IA están claramente separados. Esto facilita cualquier modificación o expansión en cualquiera de ellos sin afectar al resto del sistema.
- **Facilidad de Cambio:** Cualquier modificación futura (por ejemplo, pasar a un modelo donde el usuario firma la transacción de compra) será más sencilla porque ya se tiene:
  - La experiencia de interactuar con contratos.
  - La base de datos estructurada.
  - Los flujos de API definidos.
  - La integración con Web3 probada.

En conclusión, el MVP actual no es una versión incompleta, sino una implementación estratégica que demuestra el valor central del producto (ticket como NFT) de la manera más directa y verificable posible. Proporciona una base técnicamente sólida y coherente con los objetivos del MVP para futuras iteraciones.