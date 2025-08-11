# Guía de Integración Frontend - Actualizaciones del MVP

Este documento describe las nuevas características y cambios en la API del backend que el equipo de frontend debe integrar. Estas actualizaciones mejoran la simulación del flujo de negocio completo (compra, pago, retiro de fondos) para el MVP de la Ticketera IA + Blockchain.

## 1. Nuevos Campos en Modelos de Datos

### 1.1. Modelo `Ticket`
Se han añadido dos nuevos campos a la tabla `tickets` en el backend:
*   `purchase_date` (Tipo: `string`, Formato: ISO 8601 DateTime): La fecha y hora en que se realizó la compra del ticket. Este valor se establece automáticamente al comprar un ticket.
*   `is_paid` (Tipo: `boolean`): Un indicador que simula si el ticket ha sido pagado. Siempre será `true` para tickets comprados a través del endpoint de compra.

**Impacto:** Cuando se obtengan listas de tickets (por ejemplo, mediante `GET /users/me/tickets`), estos nuevos campos pueden estar presentes en objetos futuros si se extiende la API. Por ahora, el endpoint existente no los devuelve, pero es bueno conocer su existencia para futuras mejoras.

### 1.2. Modelo `Event`
Se han añadido dos nuevos campos a la tabla `events`:
*   `total_revenue` (Tipo: `number`): Representa la cantidad total de ingresos generados por la venta de tickets para este evento. Se incrementa automáticamente cada vez que se compra un ticket.
*   `is_funds_withdrawn` (Tipo: `boolean`): Un indicador que simula si el organizador ha "retirado" los fondos recaudados. Se establece en `true` cuando se llama al nuevo endpoint de simulación de retiro.

**Impacto:** Estos campos son relevantes para el panel del organizador. Pueden usarse para mostrar estadísticas de ventas o el estado de retiro de fondos.

## 2. Actualización del Endpoint de Compra de Tickets

El endpoint `POST /events/{event_id}/purchase` ha sido modificado para incluir una simulación de pago.

### 2.1. Cambios en la Respuesta

La respuesta del endpoint ahora incluye información adicional sobre la simulación de pago:

**Nuevo Cuerpo de Respuesta:**
```json
{
  "message": "Ticket purchased and minted successfully",
  "transaction_hash": "0x...",
  "ticket_id": 123,
  "paid_amount": 25.50,        // <--- NUEVO
  "purchase_date": "2023-10-27T10:00:00Z" // <--- NUEVO
}
```

**Detalles:**
*   `paid_amount` (Tipo: `number`): El precio del ticket que se "cobró" en esta simulación.
*   `purchase_date` (Tipo: `string`): La fecha y hora ISO 8601 en que se registró esta compra simulada.

**Acción del Frontend:**
*   Actualizar la lógica de manejo de la respuesta de este endpoint para procesar y mostrar los nuevos campos (`paid_amount`, `purchase_date`).
*   Esta información puede mostrarse al usuario como confirmación de la compra.

## 3. Nuevo Endpoint: Simulación de Retiro de Fondos

Se ha añadido un nuevo endpoint para que los organizadores puedan "simular" el retiro de los ingresos generados por la venta de tickets de un evento.

### 3.1. `POST /events/{event_id}/simulate-withdrawal` (Protegido, solo Organizador y dueño del evento)

*   **Descripción:** Marca los fondos recaudados para un evento específico como "retirados" en la base de datos del backend. Esto es una simulación y no involucra transacciones reales en la blockchain.
*   **Parámetros de la Ruta:**
    *   `event_id` (integer): El ID del evento del que se quieren "retirar" los fondos.
*   **Encabezados:**
    *   `Authorization: Bearer <token>` (JWT del organizador).
*   **Cuerpo de la Solicitud:** Ninguno.
*   **Respuesta Exitosa (200 OK):**
    ```json
    {
      "message": "Funds for event 'Concierto de Rock' marked as withdrawn (simulated).",
      "amount": 1275.00
    }
    ```
*   **Posibles Errores:**
    *   `401 Unauthorized`: Si el usuario no está autenticado.
    *   `403 Forbidden`: Si el usuario no es el dueño del evento o no tiene el rol de `ORGANIZADOR`.
    *   `404 Not Found`: Si el `event_id` no existe.
    *   `400 Bad Request`: Si los fondos para este evento ya han sido marcados como "retirados".

**Acción del Frontend:**
*   En el panel del organizador, para eventos que tengan `total_revenue > 0`, añadir un botón o acción "Simular Retiro de Fondos".
*   Este botón debe llamar a este nuevo endpoint.
*   Tras una respuesta exitosa, actualizar la interfaz para reflejar que los fondos han sido "retirados" (por ejemplo, deshabilitando el botón y mostrando un mensaje). Puedes almacenar este estado localmente o volver a consultar los detalles del evento si el backend no lo devuelve directamente en la respuesta.

## 4. Consideraciones Finales

*   Estas actualizaciones están diseñadas para hacer que el MVP demuestre un ciclo de negocio completo sin añadir la complejidad de transacciones de pago reales en la blockchain.
*   El frontend no necesita cambios en la integración con billeteras para estas nuevas simulaciones.
*   Es responsabilidad del frontend manejar adecuadamente los nuevos datos y estados devueltos por la API.