# ══════════════════════════════════════════════════════════════
# STEP 1: IMPORTS
# ══════════════════════════════════════════════════════════════

import json                          # To convert Python dicts to JSON strings
import contextlib                    # For managing server startup/shutdown lifecycle
from fastapi import FastAPI          # The web framework (like Express.js for Python)
from fastapi.responses import PlainTextResponse  # Simple text response for health check
from mcp.server.fastmcp import FastMCP           # MCP's high-level server class


# ══════════════════════════════════════════════════════════════
# STEP 2: CREATE THE MCP SERVER
# ══════════════════════════════════════════════════════════════

# FastMCP handles all MCP protocol stuff — JSON-RPC parsing, 
# session management, tool registration, schema generation.
#
# stateless_http=True → Each request is independent (no sessions)
#                        This makes it scalable — any replica can handle any request
#
# json_response=True  → Returns plain JSON instead of SSE streams
#                        Simpler, more compatible with load balancers

mcp = FastMCP(
    name="jamiat-tracker",          # Server name (shown to clients during handshake)
    stateless_http=True,       # No session persistence (scalable)
    json_response=True,        # Plain JSON responses (not SSE streams)
    streamable_http_path="/",  # Serve at root of mount point (avoids /mcp/mcp)
)


# ══════════════════════════════════════════════════════════════
# STEP 3: DEFINE Jamiat DATA (replace with real DB later)
# ══════════════════════════════════════════════════════════════

PROJECTS = {
    "jamiat":  {"name": "Jamiat",     "website status": "live", "dashboard status": "live",      "deployment platform": "Vercel",       "cost": "$20/mo"},
    "sama":       {"name": "SAMA",       "website status": "live", "dashboard status": "development",      "deployment platform": "Vercel",       "cost": "$20/mo"},
    "safe":       {"name": "SAFE",       "website status": "live", "dashboard status": "live",      "deployment platform": "Vercel",       "cost": "$20/mo"},
    "next":       {"name": "NEXT",       "website status": "live", "dashboard status": "development",      "deployment platform": "Vercel",       "cost": "$20/mo"},
    "hamqadam":  {"name": "Hamqadam",   "website status": "live", "dashboard status": "live",      "deployment platform": "Vercel + Sanity", "cost": "$45/mo"},
}


# ══════════════════════════════════════════════════════════════
# STEP 4: REGISTER TOOLS (functions the AI can CALL)
# ══════════════════════════════════════════════════════════════

# TOOL 1: Get a specific project
@mcp.tool()
def get_project(project_id: str) -> str:
    """Get the current status and details of a project by its ID.
    
    Available project IDs: jamiat, sama, safe, next, hamqadam
    """
    # ↑ This docstring becomes the tool DESCRIPTION
    #   The AI reads this to decide WHEN to use this tool
    
    # ↑ project_id: str → becomes JSON Schema: {"type": "string"}
    #   The AI knows it needs to pass a string
    
    project = PROJECTS.get(project_id.lower())
    if not project:
        return f"❌ Project '{project_id}' not found. Available: {list(PROJECTS.keys())}"
    return json.dumps(project, indent=2)


# TOOL 2: List all projects
@mcp.tool()
def list_projects() -> str:
    """List all projects in the Jamiat IT Department with their current status."""
    
    # No parameters needed → AI calls this with empty arguments
    summary = []
    for pid, info in PROJECTS.items():
        summary.append(f"• {info['name']} ({pid}) - {info['website status']} - {info['dashboard status']} - {info['deployment platform']} - {info['cost']}")
    return "\n".join(summary)


# TOOL 3: Get total hosting cost
@mcp.tool()
def get_total_cost() -> str:
    """Calculate the total monthly hosting cost across all projects."""
    
    total = 0
    breakdown = []
    for pid, info in PROJECTS.items():
        # Extract number from cost string like "$25/mo"
        cost_str = info["cost"].replace("$", "").replace("/mo", "")
        cost = float(cost_str) if cost_str != "0" else 0
        total += cost
        breakdown.append(f"  {info['name']}: {info['cost']}")
    
    result = f"Monthly Hosting Breakdown:\n"
    result += "\n".join(breakdown)
    result += f"\n\nTotal: ${total}/mo"
    return result


# TOOL 4: Search projects by status
@mcp.tool()
def search_by_status(website_status: str = None, dashboard_status: str = None) -> str:
    """Find all projects with a specific website and/or dashboard status.
    
    Valid statuses: live, development
    You can filter by website_status, dashboard_status, or both.
    """
    matches = {}
    for pid, info in PROJECTS.items():
        website_match = website_status is None or info["website status"].lower() == website_status.lower()
        dashboard_match = dashboard_status is None or info["dashboard status"].lower() == dashboard_status.lower()
        if website_match and dashboard_match:
            matches[pid] = info
    
    if not matches:
        return f"No projects found with website_status='{website_status}', dashboard_status='{dashboard_status}'"
    return json.dumps(matches, indent=2)


# ══════════════════════════════════════════════════════════════
# STEP 5: REGISTER RESOURCES (data the AI can READ)
# ══════════════════════════════════════════════════════════════

@mcp.resource("tracker://projects/all")
def all_projects_resource() -> str:
    """Complete project database as JSON."""
    # Resources are READ-ONLY — no side effects
    # AI can request this URI to get data without calling a tool
    return json.dumps(PROJECTS, indent=2)


# ══════════════════════════════════════════════════════════════
# STEP 6: REGISTER PROMPTS (reusable prompt templates)
# ══════════════════════════════════════════════════════════════

@mcp.prompt()
def monthly_report() -> str:
    """Generate a monthly IT department status report."""
    data = json.dumps(PROJECTS, indent=2)
    return f"""You are the IT Department Manager at Jamiat. 
Generate a professional monthly status report based on this project data:
{data}

Include: Executive summary, per-project updates, hosting costs, and next month's priorities.
Keep it concise and professional."""


# ══════════════════════════════════════════════════════════════
# STEP 7: CREATE THE FASTAPI APP WITH LIFESPAN
# ══════════════════════════════════════════════════════════════

# WHAT IS LIFESPAN?
# -----------------
# It's FastAPI's way of running setup code when the server STARTS
# and cleanup code when the server STOPS.
#
# Here, we need to start the MCP session manager when FastAPI boots up.
# The session manager handles incoming MCP connections and routes them
# to the right tools/resources.
#
# Think of it like: "Turn on the MCP engine when the web server starts,
# turn it off when the web server stops."

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    # session_manager.run() starts the MCP protocol handler
    # It listens for incoming JSON-RPC messages and dispatches them
    async with mcp.session_manager.run():
        yield  # ← Server is running, handling requests here
    # ── SHUTDOWN ──
    # When we exit this block, MCP cleans up connections


# Create FastAPI app with the lifespan
app = FastAPI(
    title="Jamiat IT MCP Server",    # Shows in auto-generated docs at /docs
    version="1.0.0",
    lifespan=lifespan,               # Attach the startup/shutdown lifecycle
)


# ══════════════════════════════════════════════════════════════
# STEP 8: MOUNT MCP + ADD HEALTH CHECK
# ══════════════════════════════════════════════════════════════

# MOUNTING = attaching the MCP app at a specific URL path
# After this, all MCP communication happens at POST /mcp
#
# streamable_http_app() returns a Starlette ASGI app that:
#   - Accepts POST requests with JSON-RPC messages
#   - Routes them to your tools/resources/prompts
#   - Returns JSON-RPC responses

app.mount("/mcp", mcp.streamable_http_app())


# Health check endpoint — hosting platforms ping this to know your server is alive
@app.get("/health")
async def health():
    return PlainTextResponse("OK")


# Root endpoint — friendly info page
@app.get("/")
async def root():
    return {
        "server": "Jamiat IT MCP Server",
        "status": "running",
        "mcp_endpoint": "/mcp",
        "docs": "/docs",
        "tools": ["get_project", "list_projects", "get_total_cost", "search_by_status"],
}