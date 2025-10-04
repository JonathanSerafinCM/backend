# Dockerized backend setup

This document explains how to run the Ticketera backend alongside PostgreSQL using Docker Compose.

## 1. Prerequisites

- Docker Desktop with WSL 2 backend enabled (or Docker Engine inside WSL).
- Access to a Polygon Amoy (or compatible) RPC endpoint and deployed `TicketManager` contract so the blockchain features can work.

## 2. Prepare environment variables

1. Duplicate the provided `.env.example` file and rename the copy to `.env`.
2. Update the placeholders:

    - `POSTGRES_*` values define the credentials for the bundled PostgreSQL instance.
    - `SECRET_KEY` secures JWT generation.
    - `TESTNET_RPC_URL`, `CONTRACT_ADDRESS`, and `PRIVATE_KEY` must point to a working RPC endpoint, contract address, and wallet private key that has funds on the target network.
    - `BACKEND_HOST_PORT` lets you expose the API on a different host port if `8000` is already taken (for example, set it to `8080`).

## 3. Build and run

From the repository root (`backend` folder), run the following command from your WSL shell:

```bash
docker compose up --build
```

This will launch two containers:

- `ticketera-db`: PostgreSQL 16 instance, exposed on port `5432`.
- `ticketera-backend`: FastAPI app served by Uvicorn on <http://localhost:8000/>.

The backend service waits for the database to become healthy before starting.

## 4. Development tips

- The backend container mounts the repository directory, so changes to Python files are visible inside the container. Restart the service to pick up code updates.
- Attach to the backend logs with:

  ```bash
  docker compose logs -f backend
  ```

- To seed or inspect the database, connect with any PostgreSQL client using the credentials defined in your `.env` file.

## 5. Stopping and cleanup

- Stop services: `docker compose down`
- Remove data volume as well: `docker compose down -v`

> **Note:** The blockchain-dependent endpoints still require the external network you configured in `.env`. If you only need the REST API without blockchain calls, you can point `TESTNET_RPC_URL` to a local node such as Ganache running at `http://127.0.0.1:8545` and use its private key / contract deployment.
