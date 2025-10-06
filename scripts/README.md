# Scripts utilitarios

## `import_ticketmaster_events.py`

Script CLI que importa el listado actual de eventos publicos de Ticketmaster
(Descubre Valencia) y los vuelca en la base de datos del backend bajo un
organizador compartido.

### Requisitos
- Dependencias del backend instaladas (`pip install -r requirements.txt` o activar `venv`).
- Variable `DATABASE_URL` apuntando a la misma instancia que usa el backend. Si no existe, el script cae en `sqlite:///test.db`.
- Acceso a red saliente para llamar a `ticketmaster.es`.
- Si usas Docker Compose, entra al contenedor `ticketera-backend` antes de ejecutar los comandos:
  ```bash
  docker exec -it ticketera-backend bash
  ```

### Ejecucion recomendada (dentro del contenedor)

1. **Dry-run para validar sin tocar la base de datos**
   ```bash
   python scripts/import_ticketmaster_events.py \
     --organiser-email organizador@example.com \
     --organiser-password organizador123 \
     --limit 3 \
     --dry-run
   ```

   Salida esperada (se omite parte del texto):
   ```
       would_create :: Lasso - Valencia (2025-10-09)
       would_create :: Kerala Dust (2025-10-22)
       would_create :: Paul Alone (2025-10-30)

   Summary:
     Would Create: 3
   Dry-run mode: no database changes were applied.
   ```

2. **Import real (cuando quieras poblar la base)**
   ```bash
   python scripts/import_ticketmaster_events.py \
     --organiser-email organizador@example.com \
     --organiser-password organizador123 \
     --total-tickets 500
   ```

   Si el usuario organizador no existe, el script lo crea automaticamente. Los eventos se actualizan
   por coincidencia de nombre + fecha, preservando la cuenta `organizador@example.com` como owner.

### Opciones adicionales
- `--city-url` permite apuntar a otra ciudad de Ticketmaster Discover.
- `--keep-remote-images` evita descargar las imagenes y mantiene la URL remota.
- `--limit N` limita el numero de eventos importados.
- `--total-tickets` fija cuantos boletos se asignan por evento (por defecto 500).

Cada ejecucion valida/crea el usuario organizador indicado y realiza *upsert*
sobre eventos coincidentes por nombre y fecha; se actualizan descripcion, lugar,
precio, categoria e imagen cuando cambian.
