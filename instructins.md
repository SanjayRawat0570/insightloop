
# InsightLoop — Full Stack Build

Build a production-ready AI-native Business Intelligence platform called **InsightLoop**. 
Users connect data sources, ask questions in plain English, and AI agents generate SQL, 
analyze results, pick visualizations, write narrative commentary, and compile PDF reports.

---

## Tech Stack

**Frontend:** Next.js 14 (App Router), TypeScript, TailwindCSS, shadcn/ui, Recharts, 
Socket.io-client, React Query, Zod

**Backend:** FastAPI, Python 3.11+, LangChain, LangGraph, langchain-anthropic (Claude), 
LangSmith, SQLAlchemy, Alembic, Celery, Redis, WeasyPrint, SendGrid, boto3, Pandas

**Database:** PostgreSQL (metadata), Redis (cache + Celery broker), S3-compatible (reports)

**AI Model:** claude-sonnet-4-20250514 via langchain-anthropic

---

## Project Structure to Scaffold

```
insightloop/
├── frontend/
│   ├── app/
│   │   ├── (auth)/login/page.tsx
│   │   ├── connect/page.tsx
│   │   ├── chat/page.tsx
│   │   ├── dashboard/page.tsx
│   │   └── reports/page.tsx
│   ├── components/
│   │   ├── ChatPanel.tsx
│   │   ├── AgentTrace.tsx
│   │   ├── ChartTile.tsx
│   │   └── ReportScheduler.tsx
│   └── lib/
│       └── api.ts
│
└── backend/
    ├── agents/
    │   ├── query_writer.py
    │   ├── analyst.py
    │   ├── chart_selector.py
    │   ├── narrative.py
    │   └── compiler.py
    ├── graph/
    │   └── pipeline.py
    ├── api/
    │   ├── routes/
    │   │   ├── query.py
    │   │   ├── sources.py
    │   │   └── reports.py
    │   └── main.py
    ├── tasks/
    │   └── scheduler.py
    ├── db/
    │   ├── models.py
    │   └── migrations/
    └── utils/
        ├── pdf_gen.py
        ├── email.py
        └── schema_parser.py
```

---

## Backend — Detailed Implementation

### `backend/db/models.py`
SQLAlchemy models with these tables:
- `users` — id (UUID PK), email, hashed_password, plan (free/pro), created_at
- `data_sources` — id, user_id (FK), name, type (enum: postgres/mysql/csv/api/sheets), 
  connection_config (JSON, encrypted with Fernet), is_active, created_at
- `queries` — id, user_id (FK), source_id (FK), natural_language, generated_sql, 
  result_cache (JSON), execution_ms, created_at
- `dashboards` — id, user_id (FK), name, layout_json (JSON array of tile configs), created_at
- `reports` — id, user_id (FK), dashboard_id (FK), name, schedule_cron, last_run_at, 
  output_s3_url, recipients (JSON array of emails), is_active, created_at
- `agent_runs` — id, query_id (FK), agent_name, input_data (JSON), output_data (JSON), 
  tokens_used, duration_ms, error, created_at

Use Alembic for migrations. Create `env.py` and an initial migration.

---

### `backend/agents/query_writer.py`
```python
# LangChain + Claude agent that converts natural language to SQL
# Input: {question: str, schema: str, dialect: str}
# Output: {sql: str, explanation: str}
# Use ChatAnthropic with a detailed system prompt
# Include few-shot examples for common query patterns
# Validate output is syntactically valid SQL before returning
# Raise QueryWriterError with helpful message if it cannot generate valid SQL
```

System prompt must include:
- Role: expert SQL engineer
- Always use table aliases
- Never use SELECT * — always specify columns
- Add LIMIT 1000 to prevent runaway queries
- Return ONLY the SQL, no markdown fences
- Handle aggregations, JOINs, date functions, window functions

---

### `backend/agents/analyst.py`
```python
# Input: {sql_result: list[dict], question: str}
# Output: {trend: str, anomalies: list[str], summary: str, 
#           key_metric: str, key_value: Any, pct_change: float | None}
# Use Claude to identify the single most important finding
# Detect outliers statistically (>2 std dev) before sending to Claude
# Return structured JSON validated with Pydantic
```

---

### `backend/agents/chart_selector.py`
```python
# Input: {sql_result: list[dict], analysis: dict, question: str}
# Output: {chart_type: str, x_axis: str, y_axis: str | list,
#           color_by: str | None, title: str, subtitle: str}
# Rules encoded in system prompt:
#   - time series data → line chart
#   - ≤2 categories comparison → bar chart  
#   - part of whole, ≤6 slices → pie chart
#   - two numeric columns → scatter
#   - >5 columns or pivot data → heatmap
#   - everything else → table
# Return structured JSON validated with Pydantic
```

---

### `backend/agents/narrative.py`
```python
# Input: {analysis: dict, chart_config: dict, question: str}
# Output: {headline: str, supporting: list[str], recommendation: str, tone: str}
# Claude writes executive-level commentary
# Tone: direct, no jargon, action-oriented
# Headline ≤ 12 words
# Two supporting sentences max
# One clear recommended action
```

---

### `backend/agents/compiler.py`
```python
# Input: full InsightState
# Output: {report_json: dict} with structure:
#   {title, generated_at, executive_summary, sections: [
#     {title, chart_config, narrative, data_table, sql_used}
#   ]}
# Claude writes a 2-sentence executive summary across all sections
# Does NOT generate PDF itself — triggers pdf_gen utility
```

---

### `backend/graph/pipeline.py`
LangGraph `StateGraph` with this `InsightState` TypedDict:
```python
class InsightState(TypedDict):
    question: str
    source_id: str
    schema: str
    dialect: str
    sql: str
    sql_result: list[dict]
    analysis: dict
    chart_config: dict
    narrative: dict
    report: dict
    error: str | None
    current_node: str  # for streaming progress to frontend
```

Nodes (in order):
1. `query_writer_node` — calls QueryWriterAgent
2. `sql_executor_node` — deterministic, runs SQL against user's data source, 
   enforces LIMIT 1000, catches exceptions and sets state.error
3. `data_analyst_node` — calls AnalystAgent
4. `chart_selector_node` — calls ChartSelectorAgent
5. `narrative_node` — calls NarrativeAgent
6. `compiler_node` — calls CompilerAgent

Add conditional edge after `sql_executor_node`: if `state.error` is set, 
route to `error_node` (returns friendly error JSON) instead of continuing.

Compile with `checkpointer=MemorySaver()` for conversation memory.

Use LangSmith callbacks on every node:
```python
from langsmith import traceable
```

---

### `backend/api/main.py`
FastAPI app with:
- CORS configured for frontend origin
- JWT auth middleware (python-jose)
- WebSocket endpoint `/ws/{client_id}` — streams agent node updates as JSON events:
```json
  {"event": "node_start", "node": "query_writer", "timestamp": "..."}
  {"event": "node_complete", "node": "query_writer", "output": {...}, "timestamp": "..."}
  {"event": "pipeline_complete", "result": {...}}
  {"event": "pipeline_error", "error": "..."}
```
- Mount routers from `api/routes/`
- Lifespan context manager for DB pool and Redis connection
- `/health` endpoint

---

### `backend/api/routes/query.py`
```
POST /api/query
  Body: {question: str, source_id: str, client_id: str}
  → Validates source ownership
  → Fetches schema via schema_parser
  → Runs pipeline via BackgroundTasks (streams updates over WebSocket)
  → Returns {query_id: str} immediately

GET /api/query/{query_id}
  → Returns stored query with result, chart_config, narrative

GET /api/query/history
  → Returns paginated list of user's past queries
```

---

### `backend/api/routes/sources.py`
```
POST /api/sources
  Body: {name, type, connection_config}
  → Validates connection (actually connects and runs SELECT 1)
  → Encrypts connection_config with Fernet before storing
  → Returns source metadata (never returns raw credentials)

GET /api/sources
  → Returns user's sources (no credentials in response)

DELETE /api/sources/{source_id}

POST /api/sources/{source_id}/schema
  → Returns parsed schema: {tables: [{name, columns: [{name, type, nullable}]}]}
```

---

### `backend/api/routes/reports.py`
```
POST /api/reports
  Body: {name, dashboard_id, schedule_cron, recipients}
  → Validates cron expression
  → Schedules Celery periodic task
  → Returns report config

GET /api/reports
GET /api/reports/{report_id}

POST /api/reports/{report_id}/run
  → Manually triggers report immediately

DELETE /api/reports/{report_id}
  → Also removes Celery periodic task
```

---

### `backend/tasks/scheduler.py`
Celery app configured with Redis broker. Tasks:
- `run_scheduled_report(report_id: str)` — fetches report config, re-runs the full 
  LangGraph pipeline for each query in the dashboard, compiles PDF, uploads to S3, 
  sends email via SendGrid
- `cleanup_old_results()` — periodic task, deletes result_cache older than 7 days

---

### `backend/utils/schema_parser.py`
```python
# Connects to a user's data source and extracts schema
# Supports: PostgreSQL, MySQL, SQLite (for dev), CSV (pandas dtypes)
# Returns: {dialect: str, tables: [{name, columns: [{name, type, sample_values}]}]}
# Include sample_values (first 3 distinct non-null values per column)
# These go into the Query Writer prompt for better SQL generation
```

---

### `backend/utils/pdf_gen.py`
```python
# WeasyPrint-based PDF generator
# Input: report_json dict + rendered chart images (base64 PNG from Chart.js server-side)
# Use Jinja2 template for the HTML → PDF pipeline
# Template sections: cover page, executive summary, one page per section 
#   (chart image + narrative + data table)
# Return: bytes (PDF binary)
# Upload to S3 and return presigned URL (7-day expiry)
```

---

### `backend/utils/email.py`
```python
# SendGrid client
# send_report_email(recipients: list[str], report_name: str, pdf_url: str, summary: str)
# HTML email template with: report name, executive summary excerpt, "View Report" button
# Plain text fallback
```

---

## Frontend — Detailed Implementation

### `frontend/lib/api.ts`
Typed API client using `fetch` with:
- Base URL from `NEXT_PUBLIC_API_URL` env var
- JWT token injection from localStorage
- Automatic 401 → redirect to /login
- Generic `apiRequest<T>()` helper
- Typed functions for every endpoint:
  - `connectSource()`, `getSources()`, `deleteSource()`, `getSchema()`
  - `submitQuery()`, `getQuery()`, `getQueryHistory()`
  - `getDashboards()`, `saveDashboard()`
  - `getReports()`, `createReport()`, `runReport()`, `deleteReport()`
- WebSocket helper: `createAgentSocket(clientId, onEvent)` → returns socket instance

---

### `frontend/components/ChatPanel.tsx`
The main query interface. Features:
- Text input with send button and keyboard shortcut (Cmd+Enter)
- Message history: user messages on right, AI responses on left
- Each AI response card shows: AgentTrace (live during processing), 
  then final ChartTile + narrative text when complete
- "Suggested questions" chips when chat is empty (populated from data source schema)
- Copy SQL button on each response
- "Save to dashboard" button that opens a modal to pick/create a dashboard
- Re-run query button
- Source selector dropdown at top (pick which connected data source to query)
- Loading state: pulsing skeleton while pipeline runs

---

### `frontend/components/AgentTrace.tsx`
Live pipeline progress panel shown during query execution. Features:
- Connects to WebSocket on mount using `clientId` prop
- Shows 5 pipeline steps as a vertical stepper:
  1. Query Writer — "Generating SQL..."
  2. SQL Executor — "Running query..."
  3. Data Analyst — "Analyzing results..."
  4. Chart Selector — "Choosing visualization..."
  5. Narrative — "Writing commentary..."
- Each step: idle (gray circle) → active (spinning, blue) → complete (green check) → error (red X)
- When a step completes, show a one-line preview of its output 
  (e.g. "Generated SELECT statement with 2 JOINs")
- Collapses after pipeline completes, replaced by the result card
- Show total execution time on completion

---

### `frontend/components/ChartTile.tsx`
Renders a single data visualization. Props: `{chartConfig, data, narrative, isLoading}`. Features:
- Renders the correct Recharts component based on `chartConfig.chart_type`:
  - `line` → LineChart with smooth curves
  - `bar` → BarChart (vertical by default, horizontal if >8 categories)
  - `pie` → PieChart with custom label
  - `scatter` → ScatterChart
  - `table` → sortable HTML table with pagination (25 rows/page)
- Chart title from `chartConfig.title`
- Narrative headline below title, supporting text in smaller font
- "Recommendation" pill badge at bottom
- Export menu (top-right): Download PNG, Download CSV, Copy SQL
- Responsive — uses `ResponsiveContainer` from Recharts
- Skeleton loading state

---

### `frontend/components/ReportScheduler.tsx`
Modal component for scheduling automated reports. Features:
- Report name input
- Dashboard selector (dropdown of user's saved dashboards)
- Schedule options: Daily / Weekly / Monthly / Custom cron
  - Custom cron: text input + human-readable preview ("Every Monday at 9:00 AM")
- Recipients: email chip input (add multiple, validate email format)
- "Send test now" button — triggers immediate run
- Shows last run status + link to download last PDF
- Toggle to enable/disable schedule without deleting

---

### `frontend/app/(auth)/login/page.tsx`
Clean login page with:
- Email + password fields
- "Sign in" button → POST /api/auth/login → stores JWT
- "Create account" link → POST /api/auth/register
- Redirect to /chat on success

---

### `frontend/app/connect/page.tsx`
Data source connection page:
- Grid of source type cards: PostgreSQL, MySQL, CSV Upload, REST API, Google Sheets
- Clicking a card opens a slide-over panel with the relevant connection form:
  - **PostgreSQL/MySQL**: host, port, database, username, password, SSL toggle
  - **CSV**: file upload (drag-and-drop), preview first 5 rows after upload
  - **REST API**: URL, auth type (none/API key/Bearer), headers
  - **Google Sheets**: sheet URL, service account JSON upload
- "Test connection" button — shows success/error inline
- "Save connection" button — only enabled after successful test
- List of existing connected sources below the grid:
  - Source name, type icon, status badge, last used, delete button
  - "Browse schema" button — opens schema explorer showing tables and columns

---

### `frontend/app/chat/page.tsx`
Main layout:
- Left sidebar: source selector + query history list (click to reload a past query)
- Main area: `<ChatPanel />` component
- Keyboard shortcut: `Cmd+K` focuses the query input

---

### `frontend/app/dashboard/page.tsx`
Dashboard builder:
- Top bar: dashboard name (editable), "Save" button, "Schedule Report" button
- Drag-and-drop grid (react-grid-layout or similar): tiles are `<ChartTile />` instances
- "Add chart" button → opens query history picker to pull in a saved result as a tile
- Each tile has: resize handles, drag handle, remove (×) button, "Refresh" button
- Empty state: illustration + "Run a query in Chat to add charts here"

---

### `frontend/app/reports/page.tsx`
Report management page:
- Table of scheduled reports: Name, Dashboard, Schedule, Last run, Status, Actions
- "New report" button → opens `<ReportScheduler />` modal
- Each row: Edit, Run now, Download last PDF, Delete
- "Run now" shows a toast with progress, then a download link when done

---

## Environment Variables

### Backend `.env`
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/insightloop
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
LANGCHAIN_API_KEY=...              # LangSmith
LANGCHAIN_PROJECT=insightloop
FERNET_KEY=...                     # for encrypting DB credentials
JWT_SECRET=...
JWT_ALGORITHM=HS256
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=insightloop-reports
SENDGRID_API_KEY=...
FROM_EMAIL=reports@insightloop.io
FRONTEND_URL=http://localhost:3000
```

### Frontend `.env.local`
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Docker Setup

Create `docker-compose.yml` with services:
- `postgres` — postgres:16, with healthcheck
- `redis` — redis:7-alpine
- `backend` — builds from `./backend`, depends on postgres + redis, 
  runs `uvicorn api.main:app --reload`
- `worker` — same image, runs `celery -A tasks.scheduler worker --loglevel=info`
- `beat` — same image, runs `celery -A tasks.scheduler beat --loglevel=info`
- `frontend` — builds from `./frontend`, runs `next dev`

---

## Python Dependencies (`backend/requirements.txt`)
```
fastapi>=0.111
uvicorn[standard]>=0.30
sqlalchemy[asyncio]>=2.0
alembic>=1.13
asyncpg>=0.29
psycopg2-binary>=2.9
langchain>=0.2
langchain-anthropic>=0.1
langgraph>=0.1
langsmith>=0.1
celery[redis]>=5.4
redis>=5.0
pandas>=2.2
weasyprint>=62
jinja2>=3.1
sendgrid>=6.11
boto3>=1.34
python-jose[cryptography]>=3.3
passlib[bcrypt]>=1.7
cryptography>=42
pydantic>=2.7
pydantic-settings>=2.3
python-multipart>=0.0.9
websockets>=12
httpx>=0.27
```

---

## Build Instructions for Claude Code

1. Scaffold the full directory structure first
2. Create all Python files with complete implementations (no placeholder `pass` statements 
   or `# TODO` — write real working code)
3. Create all TypeScript/React components with real implementations
4. Wire up all imports correctly — no broken import paths
5. Create `docker-compose.yml` and both `.env.example` files
6. Create `backend/requirements.txt` and `frontend/package.json`
7. Create `README.md` with: project overview, setup steps, environment variable docs, 
   how to run locally with Docker

## Critical implementation rules
- Every agent must have proper error handling and Pydantic output validation
- Every API route must validate JWT and check resource ownership before acting
- Never log or return raw database credentials
- SQL executor must enforce LIMIT 1000 and run in a read-only transaction
- All DB operations use async SQLAlchemy (asyncpg driver)
- WebSocket events must be sent for every state transition so the frontend AgentTrace 
  updates in real time
- ChartTile must handle empty result sets gracefully with an empty state message


