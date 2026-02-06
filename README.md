# jamiat-mcp-server

A simple MCP server for managing Jamiat's IT projects.

## Setup

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Run the server:

   ```bash
   fastapi dev server.py
    ```

3. Test with MCP client

   ```bash
   uv run client.py
    ```

## Tech Stack

- UV
- Python
- FastAPI
- MCP Protocol


## MCP Architecture (High-Level)

The Model Context Protocol follows a **Host → Client → Server** architecture.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  HOST (e.g. Claude Desktop, ChatGPT, IDE, AI Agent)                     │
│  The application the user interacts with directly.                      │
│  - Creates & manages one or more MCP Clients                            │
│  - Controls permissions, security, and user consent                     │
│  - Integrates the AI/LLM and aggregates context from all servers        │
│                                                                         │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐  │
│  │  MCP Client A       │  │  MCP Client B       │  │  MCP Client C    │  │
│  │  (1:1 with Server)  │  │  (1:1 with Server)  │  │  (1:1 w/ Server) │  │
│  └────────┬───────────┘  └────────┬───────────┘  └────────┬─────────┘  │
│           │                       │                        │            │
└───────────┼───────────────────────┼────────────────────────┼────────────┘
            │ MCP Protocol          │ MCP Protocol           │ MCP Protocol
            │ (JSON-RPC over        │ (JSON-RPC over         │ (JSON-RPC over
            │  Streamable HTTP      │  stdio)                │  Streamable HTTP
            │  or stdio)            │                        │  or stdio)
            │                       │                        │
   ┌────────▼───────────┐ ┌────────▼───────────┐  ┌────────▼─────────┐
   │  MCP Server A       │ │  MCP Server B       │  │  MCP Server C    │
   │  (our server.py)    │ │  (e.g. GitHub MCP)  │  │  (e.g. DB MCP)   │
   │                     │ │                     │  │                  │
   │  Exposes:           │ │  Exposes:           │  │  Exposes:        │
   │  - Tools            │ │  - Tools            │  │  - Tools         │
   │  - Resources        │ │  - Resources        │  │  - Resources     │
   │  - Prompts          │ │  - Prompts          │  │  - Prompts       │
   └─────────────────────┘ └─────────────────────┘  └──────────────────┘
```

### Roles Explained

| Component | Role | In This Project |
|-----------|------|-----------------|
| **Host** | The user-facing app that runs the AI/LLM. Creates clients, enforces security, aggregates context. | Any MCP-compatible app (Claude Desktop, custom agent, etc.) |
| **Client** | Lives inside the host. Maintains a 1:1 connection with one server. Handles protocol negotiation & message routing. | `client.py` (our test client) |
| **Server** | Exposes capabilities (tools, resources, prompts) over MCP. Operates independently with focused responsibilities. | `server.py` (our FastAPI + FastMCP server) |

### MCP Primitives (What Servers Expose)

```
┌──────────────────────────────────────────────────────────┐
│                   MCP Server Primitives                   │
├──────────────┬───────────────────┬───────────────────────┤
│   Tools      │   Resources        │   Prompts             │
│              │                    │                       │
│  Model-      │  Application-      │  User-                │
│  controlled  │  controlled        │  controlled           │
│              │                    │                       │
│  Functions   │  Read-only data    │  Reusable templates   │
│  the AI can  │  the AI can load   │  for LLM interaction  │
│  CALL to     │  into context      │                       │
│  take action │  (like GET         │  (like slash          │
│  (like POST  │   endpoints)       │   commands)           │
│   endpoints) │                    │                       │
├──────────────┼───────────────────┼───────────────────────┤
│  In our      │  In our server:    │  In our server:       │
│  server:     │                    │                       │
│              │  all_projects      │  monthly_report()     │
│  get_project │  _resource()       │                       │
│  list_project│  → tracker://      │  → generates a        │
│  get_total_  │    projects/all    │    status report      │
│    cost      │                    │    template           │
│  search_by_  │                    │                       │
│    status    │                    │                       │
└──────────────┴───────────────────┴───────────────────────┘
```

### Capability Negotiation (Handshake)

When a client connects, both sides declare what they support:

```
Client                                 Server
  │                                       │
  │── initialize ────────────────────────►│
  │   "I support: sampling,               │
  │    notifications..."                  │
  │                                       │── "I support: tools,
  │                                       │    resources, prompts..."
  │◄── server capabilities ──────────────│
  │                                       │
  │── initialized (confirmation) ────────►│
  │                                       │
  │   ✅ Session ready — both sides       │
  │      know what features are available │
```

---

## Client Flow

What Happens Under the Hood (Request Flow)

```
client.py                    FastAPI (uvicorn)              FastMCP
     │                                  │                           │
     │  Step 1: Initialize (handshake)  │                           │
     │── POST /mcp ──────────────────►│                           │
     │   {"jsonrpc":"2.0",             │── routes to MCP app ────►│
     │    "method":"initialize",...}    │                           │── starts session
     │◄─── JSON response ─────────────│◄──────────────────────────│
     │                                  │                           │
     │  Step 2: List available tools    │                           │
     │── POST /mcp ──────────────────►│                           │
     │   {"method":"tools/list"}       │── routes to MCP app ────►│
     │                                  │                           │── returns tool schemas
     │◄─── JSON with tool list ────────│◄──────────────────────────│
     │                                  │                           │
     │  Step 3: Get a specific project  │                           │
     │── POST /mcp ──────────────────►│                           │
     │   {"method":"tools/call",       │── routes to MCP app ────►│
     │    "params":{"name":            │                           │── calls get_project()
     │     "get_project",              │                           │── returns result
     │     "project_id":"jamiat"}}     │                           │
     │◄─── JSON with result ───────────│◄──────────────────────────│
     │                                  │                           │
     │  Step 4: List all projects       │                           │
     │── POST /mcp ──────────────────►│                           │
     │   {"method":"tools/call",       │── routes to MCP app ────►│
     │    "params":{"name":            │                           │── calls list_projects()
     │     "list_projects"}}           │                           │── returns result
     │◄─── JSON with result ───────────│◄──────────────────────────│
     │                                  │                           │
     │  Step 5: Get total hosting cost  │                           │
     │── POST /mcp ──────────────────►│                           │
     │   {"method":"tools/call",       │── routes to MCP app ────►│
     │    "params":{"name":            │                           │── calls get_total_cost()
     │     "get_total_cost"}}          │                           │── returns result
     │◄─── JSON with result ───────────│◄──────────────────────────│
     │                                  │                           │
     │  Step 6: Search by status        │                           │
     │── POST /mcp ──────────────────►│                           │
     │   {"method":"tools/call",       │── routes to MCP app ────►│
     │    "params":{"name":            │                           │── calls search_by_status()
     │     "search_by_status",         │                           │── returns result
     │     "website_status":"live",    │                           │
     │     "dashboard_status":"live"}} │                           │
     │◄─── JSON with result ───────────│◄──────────────────────────│
```

## Server Flow

How the Server is Built (server.py architecture)

```
┌─────────────────────────────────────────────────────────────────┐
│                     server.py (8 Steps)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Imports                                                │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  json, contextlib, FastAPI, PlainTextResponse, FastMCP │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 2: Create MCP Server                                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  mcp = FastMCP(                                        │     │
│  │      "jamiat-tracker",                                 │     │
│  │      stateless_http=True,   ← no session persistence   │     │
│  │      json_response=True,    ← plain JSON (not SSE)     │     │
│  │      streamable_http_path="/"                          │     │
│  │  )                                                     │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 3: Define Data (in-memory dict)                           │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  PROJECTS = {                                          │     │
│  │      "jamiat":  { name, website status, cost, ... }    │     │
│  │      "sama":    { ... }                                │     │
│  │      "safe":    { ... }                                │     │
│  │      "next":    { ... }                                │     │
│  │      "hamqadam": { ... }                               │     │
│  │  }                                                     │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 4: Register Tools (functions AI can CALL)                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  @mcp.tool()                                           │     │
│  │  def get_project(project_id)       → project details   │     │
│  │                                                        │     │
│  │  @mcp.tool()                                           │     │
│  │  def list_projects()               → all projects      │     │
│  │                                                        │     │
│  │  @mcp.tool()                                           │     │
│  │  def get_total_cost()              → cost breakdown    │     │
│  │                                                        │     │
│  │  @mcp.tool()                                           │     │
│  │  def search_by_status(website_status, dashboard_status)│     │
│  │                                    → filtered projects │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 5: Register Resources (data AI can READ)                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  @mcp.resource("tracker://projects/all")               │     │
│  │  def all_projects_resource()       → full JSON dump    │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 6: Register Prompts (reusable templates)                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  @mcp.prompt()                                         │     │
│  │  def monthly_report()              → report template   │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 7: Create FastAPI App with Lifespan                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  @contextlib.asynccontextmanager                       │     │
│  │  async def lifespan(app):                              │     │
│  │      async with mcp.session_manager.run():             │     │
│  │          yield   ← server running, handling requests   │     │
│  │                                                        │     │
│  │  app = FastAPI(                                        │     │
│  │      title="Jamiat IT MCP Server",                     │     │
│  │      lifespan=lifespan                                 │     │
│  │  )                                                     │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  Step 8: Mount MCP + Add Endpoints                              │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  app.mount("/mcp", mcp.streamable_http_app())          │     │
│  │                                                        │     │
│  │  GET  /health  → "OK"          (health check)          │     │
│  │  GET  /        → server info   (root endpoint)         │     │
│  │  POST /mcp     → MCP protocol  (tools/resources/etc)   │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
