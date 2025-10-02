# Informe del Producto Mínimo Viable (MVP) - Ticketera IA + Blockchain

Estimado cliente,

Este documento resume el estado y las funcionalidades del Producto Mínimo Viable (MVP) de la Ticketera IA + Blockchain. Para facilitar su evaluación, se han creado dos usuarios de prueba:

*   **Organizador:** `organizador@example.com` / Contraseña: `password`
*   **Comprador:** `comprador@example.com` / Contraseña: `password`

Ambos usuarios tienen direcciones de billetera válidas y pueden ser utilizados para probar el flujo completo de creación y compra de eventos.

Puede verificar la actividad de los tickets NFT directamente en la testnet Polygon Amoy mediante el explorador de bloques OKLink, usando la dirección del contrato inteligente:
[https://www.oklink.com/es-la/amoy/address/0x10072b1913084d87d2cf53763acc21d7d642f0b7](https://www.oklink.com/es-la/amoy/address/0x10072b1913084d87d2cf53763acc21d7d642f0b7)

## 1. Resumen de Funcionalidades del MVP

El MVP implementa con éxito los tres pilares definidos para el proyecto:

*   **Gestión de Eventos y Usuarios:** Un sistema completo de autenticación y gestión de perfiles, junto con un módulo CRUD (Crear, Leer, Actualizar, Eliminar) para que los organizadores puedan gestionar sus eventos.
*   **Trazabilidad en la Blockchain:** Cada ticket se representa como un token no fungible (NFT) único en la red de prueba Polygon Amoy. Esto garantiza una propiedad verificable e inmutable.
*   **Inteligencia Artificial (Ligera):** Un sistema de recomendaciones de eventos basado en categorías y análisis de ventas simples para los organizadores.

## 2. Flujo de Trabajo del Sistema

### 2.1. Organizador crea un Evento

1.  Un usuario con el rol de "Organizador" inicia sesión en la aplicación.
2.  Utiliza la interfaz para crear un nuevo evento, proporcionando detalles como nombre, descripción, fecha, ubicación, precio y número total de tickets.
3.  Estos datos se almacenan de forma segura en una base de datos tradicional (PostgreSQL).
4.  El evento se hace visible para todos los usuarios de la plataforma.

### 2.2. Comprador Adquiere un Ticket (Flujo Actual)

1.  Un usuario con el rol de "Comprador" inicia sesión y navega por la lista de eventos disponibles.
2.  Selecciona un evento y elige la opción para adquirir un ticket.
3.  **Verificación de Disponibilidad:** El sistema verifica en su base de datos interna si aún hay tickets disponibles para ese evento.
4.  **Simulación de Pago:** Actualmente, el sistema simula el proceso de pago. Se registran datos como la fecha de compra y se actualizan los ingresos simulados del evento en la base de datos.
5.  **Minteo del NFT:** Esta es la parte clave de la integración con la blockchain. El sistema backend se conecta al contrato inteligente desplegado en la testnet Polygon Amoy.
6.  Utilizando una cuenta autorizada (manejada de forma segura por el backend), se firma y envía una transacción a la blockchain.
7.  Esta transacción ejecuta la función `safeMint` del contrato `TicketManager.sol`.
8.  Como resultado, se crea un nuevo token NFT (Ticket) y se asigna directamente a la **dirección de billetera** del comprador.
9.  El sistema actualiza su base de datos local (disminuyendo el número de tickets disponibles).
10. El comprador recibe una confirmación con un **hash de transacción**, que es la prueba inmediata de que la operación se envió a la blockchain.

### 2.3. Verificación y Trazabilidad

*   **Para el Comprador:** Puede acceder a una sección en la aplicación que le muestra todos los tickets (NFTs) asociados a su dirección de billetera. También puede ver el historial de propiedad de un ticket específico directamente desde la blockchain.
*   **Para el Organizador:** Tiene acceso a un panel de análisis simple que muestra estadísticas de ventas agrupadas por categoría de evento.
*   **Para Cualquiera (Verificación Pública):** Utilizando el explorador de bloques (OKLink), cualquier persona puede pegar el hash de la transacción o la dirección del contrato para ver todos los detalles de la operación y la existencia del NFT en la red.

## 3. Integración con la Blockchain Polygon Amoy

Un gran esfuerzo se ha realizado para integrar la aplicación con la blockchain. Esto incluye:

*   **Desarrollo del Contrato Inteligente:** Se creó y desplegó un contrato personalizado (`TicketManager.sol`) siguiendo el estándar ERC721, que es el estándar universal para NFTs.
*   **Conectividad con la Red de Prueba:** El backend se configura para conectarse a la testnet Polygon Amoy, lo que permite realizar todas las operaciones sin coste en ETH real.
*   **Gestión de Claves y Transacciones:** Se implementó de forma segura la lógica necesaria para que el backend pueda interactuar con el contrato, firmar transacciones y ejecutar acciones como el minteo de nuevos NFTs.

## 4. Justificación del Enfoque Actual como MVP

El flujo actual, donde el backend gestiona el minteo del NFT, se ha elegido estratégicamente para el MVP:

*   **Demostración Clara de Valor:** Permite demostrar de forma inmediata la funcionalidad central: que un ticket se convierte en un NFT verificable en la blockchain.
*   **Simplificación del Proceso de Compra:** Para un MVP, no requerir que el comprador firme múltiples transacciones complejas facilita las pruebas y la experiencia de usuario inicial.
*   **Base Sólida para el Futuro:** Toda la infraestructura de conexión con la blockchain ya está construida y funcionando. Esto significa que si en el futuro se desea que el comprador pague directamente con su billetera, solo se necesita una modificación focalizada en el contrato y en la lógica de compra, no una reconstrucción total.

## 5. Conclusión

El MVP entregado es una aplicación funcional que demuestra con éxito la capacidad de crear eventos, vender tickets representados como NFTs en la blockchain Polygon Amoy y verificar públicamente su trazabilidad. La integración con la tecnología blockchain es completa y está operativa, proporcionando una base sólida para futuras expansiones según sus necesidades.