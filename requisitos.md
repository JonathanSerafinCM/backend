Requerimientos Esenciales para el MVP: Ticketera con IA + Blockchain
Este documento define las funcionalidades mínimas y necesarias para el backend del Producto Mínimo Viable (MVP), asegurando que se cubran los pilares de gestión, trazabilidad (blockchain) y inteligencia (IA).

I. Core del Backend y API (Fundamentos)
Esta es la base sobre la que se construirán las demás funcionalidades. Es crucial tener un sistema de gestión de datos tradicional y bien estructurado.

1. Autenticación y Usuarios:

Gestión de Usuarios:

POST /auth/register: Endpoint para registrar nuevos usuarios (compradores u organizadores). Mínimo: email y contraseña (hasheada).

POST /auth/login: Endpoint para autenticar usuarios y devolver un token (ej. JWT) para proteger las rutas.

GET /users/me: Endpoint protegido para que un usuario obtenga su propia información.

Roles de Usuario (Simplificado para el MVP):

Comprador: Rol por defecto. Puede ver eventos y comprar tickets.

Organizador: Rol que puede crear y gestionar eventos. Para el MVP, se puede asignar manually en la base de datos.

2. Gestión de Eventos (CRUD para Organizadores):

Un organizador debe poder gestionar sus eventos. Esto se almacena en una base de datos tradicional (ej. PostgreSQL, MongoDB), NO en la blockchain. La blockchain es solo para el ticket.

Endpoints Requeridos:

POST /events: (Protegido, solo Organizador) Crea un nuevo evento.

Datos mínimos: nombre, descripcion, fecha, lugar, precio, total_tickets_disponibles.

GET /events: Lista todos los eventos disponibles para cualquier usuario.

GET /events/{event_id}: Obtiene los detalles de un evento específico.

PUT /events/{event_id}: (Protegido, solo Organizador) Actualiza los detalles de un evento.

DELETE /events/{event_id}: (Protegido, solo Organizador) Elimina un evento.

II. Módulo Blockchain (Trazabilidad del Ticket)
Aquí es donde tu código actual evoluciona. El objetivo es representar cada ticket como un activo único en la blockchain (NFT).

1. Smart Contract (Ticket como NFT - Estándar ERC721):

Tu TicketManager.sol debe ser un contrato que siga el estándar ERC721. Esto te da de forma nativa la propiedad única, la transferencia y la trazabilidad.

Funciones Esenciales en el Contrato:

safeMint(address to, uint256 tokenId, string memory tokenURI): Función para "mintear" o crear un nuevo ticket (NFT) y asignarlo a la dirección to del comprador. El tokenURI apuntará a un archivo JSON con los metadatos del ticket.

ownerOf(uint256 tokenId): Devuelve el dueño de un ticket.

tokenURI(uint256 tokenId): Devuelve la URL de los metadatos del ticket (ej. https://api.tuapp.com/metadata/tickets/1).

transferFrom(address from, address to, uint256 tokenId): Función estándar de ERC721 para transferir un ticket. Para el MVP, solo se usará para la venta inicial, pero es fundamental tenerla para la reventa futura.

2. API Endpoints para la Interacción Blockchain:

Estos endpoints son el puente entre tu aplicación y tu Smart Contract.

POST /events/{event_id}/purchase: (Protegido, solo Comprador)

Verifica que el usuario esté logueado.

Verifica en la base de datos que aún queden tickets disponibles para el evento.

(Simula el pago por ahora).

Llama a la función safeMint del Smart Contract para crear el ticket a nombre de la wallet del comprador.

Actualiza el contador de tickets disponibles en tu base de datos.

Devuelve el transaction_hash y el ticket_id (el tokenId del NFT).

GET /users/me/tickets: (Protegido)

Obtiene la dirección de la wallet del usuario logueado.

Consulta el Smart Contract para obtener todos los tokenId que le pertenecen a esa dirección.

Devuelve una lista de los tickets del usuario.

GET /tickets/{ticket_id}/history:

Consulta los eventos pasados del Smart Contract asociados a ese tokenId (ej. Transfer events).

Devuelve un historial simple de propietarios para demostrar la trazabilidad.

3. Metadatos del Ticket (Off-Chain):

GET /metadata/tickets/{ticket_id}:

Este endpoint NO interactúa con la blockchain.

Devuelve un archivo JSON con los metadatos del ticket (nombre del evento, fecha, asiento, etc.), siguiendo el estándar de metadatos de ERC721. El tokenURI del Smart Contract apuntará aquí.

III. Módulo de IA (Recomendaciones y Análisis)
Para el MVP, la "IA" será una lógica de negocio inteligente basada en los datos que ya tienes. No necesitas modelos complejos aún.

1. Recomendaciones de Eventos:

GET /events/recommendations: (Tu endpoint actual, pero con más lógica)

Lógica MVP: En lugar de datos fijos, puede implementar una de estas lógicas simples:

"Eventos en la misma categoría": Si un usuario ve un concierto de Rock, recomienda otros eventos en la categoría "Música".

"Eventos más populares": Recomienda los eventos con más tickets vendidos (consultando tu base de datos).

El endpoint podría aceptar un event_id como parámetro para basar la recomendación en ese evento.

2. Análisis de Demanda (Para el Organizador):

GET /admin/analytics/sales-by-category: (Protegido, solo Organizador)

Lógica MVP: Realiza una consulta a tu base de datos que agrupa los eventos por categoría y suma la cantidad de tickets vendidos.

Devuelve un JSON simple, como: [{"category": "Música", "tickets_sold": 150}, {"category": "Teatro", "tickets_sold": 80}]. Esto cumple con el requisito de "análisis de demandas y tendencias" de una manera simple y efectiva para el MVP. q