# NLP SQL data generator

Natural-language queries over multiple databases with a **security-first split**:

| Layer | What it sees / does |
|--------|---------------------|
| **LLM** | **Schema only** (table/column names and types). No connection strings, no credentials, no row data, no user identity. |
| **Schema API** | Keyword search → returns metadata JSON for tables your token may use. |
| **Auth API** | Issues **opaque Bearer tokens** (capabilities). The model is not told *who* you are or what others can access. |
| **Data API** | Runs **read-only** `SELECT`/`WITH` only; blocks INSERT/UPDATE/DELETE/DROP/ALTER/…; enforces per-token table allowlists. |

```mermaid
flowchart LR
  Browser[Chat UI in browser]
  Client[CLI / integrations]
  AuthAPI[/v1/auth/token]
  NlpAPI[/v1/nlp/query]
  LLM[LLM schema only]
  DataAPI[Data gateway]
  DB[(SQL Server / SQLite)]

  Browser -->|client_id + secret| AuthAPI
  Client --> AuthAPI
  AuthAPI -->|Bearer token| Browser
  Browser -->|question + token| NlpAPI
  NlpAPI --> LLM
  LLM -->|SELECT only| DataAPI
  DataAPI --> DB
```

The **browser never connects to SQL Server**. It only calls this app’s HTTP APIs.

## Chat UI (customer-facing)

```bash
pip install -e .
# optional for SQL Server: pip install -e ".[mssql]"
cp .env.example .env   # OPENAI_API_KEY + MSSQL_DATABASE_URL if using SQL Server
# edit config.yaml — add your mssql database + auth.clients entry
nlp-sql serve
```

Open **http://127.0.0.1:8000** — connect with `client_id` / `client_secret` from `config.yaml`, then ask questions in the chat.

## Quick start (CLI)

```bash
cd nlp-sql-data-generator
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python scripts/seed_sample_dbs.py
cp .env.example .env   # OPENAI_API_KEY for the LLM step
```

Get a capability token (not shown to the LLM):

```bash
nlp-sql auth --client-id sales_reader --client-secret sales-secret-change-me
export NLP_SQL_ACCESS_TOKEN="<paste token>"
nlp-sql query "Show total order amount by customer name"
```

Or run the HTTP API:

```bash
nlp-sql serve
```

```bash
# 1) Token
curl -s -X POST http://127.0.0.1:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"sales_reader","client_secret":"sales-secret-change-me"}'

# 2) Schema only (no rows)
curl -s "http://127.0.0.1:8000/v1/schema/search?q=orders+customers" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3) Read-only data (validated SQL)
curl -s -X POST http://127.0.0.1:8000/v1/data/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"database_id":"sales_db","sql":"SELECT * FROM customers LIMIT 5"}'

# 4) Full NLP pipeline (LLM + data API server-side)
curl -s -X POST http://127.0.0.1:8000/v1/nlp/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Top customers by order total"}'
```

Write/DDL attempts return **400**; out-of-scope tables return **403**.

## SQL Server (live database)

1. Install driver: `pip install -e ".[mssql]"` and [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) on the machine running **this API** (not on end-user laptops).
2. Set in `.env`:
   ```bash
   MSSQL_DATABASE_URL=mssql+pyodbc://USER:PASSWORD@host:1433/DatabaseName?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes
   ```
3. In `config.yaml`:
   ```yaml
   databases:
     - id: mssql_live
       uri: ${MSSQL_DATABASE_URL}
   auth:
     clients:
       - client_id: customer_portal
         client_secret: your-secret
         databases:
           - id: mssql_live
             tables: "*"   # or ["dbo.Orders", "Customers"]
   ```
4. Run `nlp-sql serve` and use the chat UI or API with that client.

## Configuration

- **`config.yaml`**: database URIs, retrieval, execution limits, LLM settings, **`auth.clients`** (scoped credentials), **`server.serve_chat_ui`** / **`server.cors_origins`**.
- **`NLP_SQL_ADMIN_SECRET`**: optional; `POST /v1/auth/token/admin` with header `X-Admin-Secret` to mint custom tokens (server operators only).

## Google Colab

See **`notebooks/nlp_sql_colab.ipynb`**. After loading the project, use the same token flow or call the APIs from Colab with `httpx`.

## Layout

- `frontend/` — chat UI (static; calls APIs only)
- `src/nlp_sql/auth/` — opaque tokens and table-level grants
- `src/nlp_sql/gateway/` — schema and data services (DB access stays here)
- `src/nlp_sql/routers/` — FastAPI: `/v1/auth`, `/v1/schema`, `/v1/data`, `/v1/nlp`
- `scripts/seed_sample_dbs.py` — sample SQLite files under `data/`
