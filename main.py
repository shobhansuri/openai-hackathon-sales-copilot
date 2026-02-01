import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Sales Copilot")
templates = Jinja2Templates(directory="templates")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_PATH = "agents.db"


# ============ DATABASE SETUP ============

def init_db():
    """Create tables if they don't exist"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Agents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT NOT NULL,
            voice TEXT DEFAULT 'alloy',
            vad_threshold REAL DEFAULT 0.6,
            silence_duration_ms INTEGER DEFAULT 800,
            prefix_padding_ms INTEGER DEFAULT 300,
            voice_enabled INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL,
            description TEXT,
            url TEXT,
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Tools table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            parameters TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Agent-Tools junction table (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            tool_id INTEGER NOT NULL,
            created_at TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            FOREIGN KEY (tool_id) REFERENCES tools(id),
            UNIQUE(agent_id, tool_id)
        )
    """)

    # Call Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER,
            agent_name TEXT,
            conversation TEXT,
            summary TEXT,
            coaching_tips TEXT,
            highlights TEXT,
            duration_seconds INTEGER,
            created_at TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)

    # Migration: Add url and image_url columns if they don't exist
    cursor.execute("PRAGMA table_info(products)")
    product_columns = [col[1] for col in cursor.fetchall()]
    if 'url' not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN url TEXT")
    if 'image_url' not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT")

    # Migration: Add voice_enabled column if it doesn't exist
    cursor.execute("PRAGMA table_info(agents)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'voice_enabled' not in columns:
        cursor.execute("ALTER TABLE agents ADD COLUMN voice_enabled INTEGER DEFAULT 1")

    conn.commit()
    conn.close()

    # Seed default tools
    seed_default_tools()


def seed_default_tools():
    """Seed default tools if they don't exist"""
    import json
    default_tools = [
        {
            "name": "recommend_product",
            "description": "Recommend products to the customer. IMPORTANT: Always include ALL relevant product IDs in a single call - do not make separate calls for each product. For example, if recommending 3 products, pass all 3 IDs: [1, 2, 3].",
            "parameters": json.dumps({
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of ALL product IDs to recommend in one call. Include multiple IDs when suggesting multiple products."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for the recommendation"
                    }
                },
                "required": ["product_ids"]
            })
        },
        {
            "name": "display_product",
            "description": "Display products to the customer. IMPORTANT: Include ALL product IDs you want to show in a single call - do not make separate calls. For example, to show 3 products, pass [1, 2, 3].",
            "parameters": json.dumps({
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of ALL product IDs to display in one call. Include multiple IDs to show multiple products."
                    }
                },
                "required": ["product_ids"]
            })
        }
    ]

    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    for tool in default_tools:
        cursor.execute("SELECT id FROM tools WHERE name = ?", (tool["name"],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO tools (name, description, parameters, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (tool["name"], tool["description"], tool["parameters"], now, now))

    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """Database connection context manager"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Initialize database on startup
init_db()

# ============ PYDANTIC MODELS ============

class TokenRequest(BaseModel):
    agent_id: Optional[int] = None
    prompt: Optional[str] = None  # Backward compatibility
    voice_enabled: Optional[bool] = None  # Override from UI


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    system_prompt: str
    voice: str = "alloy"
    vad_threshold: float = 0.6
    silence_duration_ms: int = 800
    prefix_padding_ms: int = 300
    voice_enabled: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    voice: Optional[str] = None
    vad_threshold: Optional[float] = None
    silence_duration_ms: Optional[int] = None
    prefix_padding_ms: Optional[int] = None
    voice_enabled: Optional[bool] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    system_prompt: str
    voice: str
    vad_threshold: float
    silence_duration_ms: int
    prefix_padding_ms: int
    voice_enabled: bool
    is_active: int
    created_at: Optional[str]
    updated_at: Optional[str]


class ScreenshotAnalysisRequest(BaseModel):
    image: str  # base64 encoded JPEG


class ProductCreate(BaseModel):
    name: str
    price: Optional[float] = None
    description: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    price: Optional[float]
    description: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    is_active: int
    created_at: Optional[str]
    updated_at: Optional[str]


class ToolCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[str] = None  # JSON string


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[str] = None


class ToolResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    parameters: Optional[str]
    is_active: int
    created_at: Optional[str]
    updated_at: Optional[str]


class AgentToolAssign(BaseModel):
    tool_ids: List[int]


class ReportGenerateRequest(BaseModel):
    agent_id: Optional[int] = None
    conversation: List[dict]  # [{role, text, timestamp}, ...]
    duration_seconds: int = 0


class ReportResponse(BaseModel):
    id: int
    agent_id: Optional[int]
    agent_name: Optional[str]
    conversation: Optional[str]
    summary: Optional[str]
    coaching_tips: Optional[str]
    highlights: Optional[str]
    duration_seconds: Optional[int]
    created_at: Optional[str]


# Sales coach system prompt (fallback)
SALES_PROMPT = """You are the user's live sales call copilot. You can see their screen and hear the conversation.

MOST IMPORTANT RULE: Only respond when there is a DIRECT QUESTION that needs answering.

WHEN TO RESPOND (in priority order):
1. A question is asked that you can answer - THIS IS MOST IMPORTANT
2. Customer raises an objection that needs a response
3. Critical buying signal the seller might miss

WHEN TO STAY COMPLETELY SILENT:
- Normal conversation - SILENT
- Small talk - SILENT
- Customer explaining things - SILENT
- Seller is handling it fine - SILENT
- No question asked - SILENT

RESPONSE FORMAT:
- Headline answer (max 6 words)
- One supporting point if needed (max 15 words)

EXAMPLES:
- "Price is $99/month. Mention the free trial."
- "They have 50 employees. Good fit for Pro plan."
- "Buying signal. Ask about timeline."

Stay silent unless you have something truly valuable to add.
"""


# ============ PAGE ROUTES ============

@app.get("/", response_class=HTMLResponse)
async def serve_home_page(request: Request):
    """Serve the main frontend page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard_page(request: Request):
    """Serve the agent management dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/products", response_class=HTMLResponse)
async def serve_products_page(request: Request):
    """Serve the product management page"""
    return templates.TemplateResponse("products.html", {"request": request})


@app.get("/tools", response_class=HTMLResponse)
async def serve_tools_page(request: Request):
    """Serve the tools management page"""
    return templates.TemplateResponse("tools.html", {"request": request})


@app.get("/reports", response_class=HTMLResponse)
async def serve_reports_page(request: Request):
    """Serve the call reports page"""
    return templates.TemplateResponse("reports.html", {"request": request})


# ============ AGENT CRUD ENDPOINTS ============

@app.get("/api/agents", response_model=List[AgentResponse])
async def list_all_agents():
    """Get all active agents"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE is_active = 1 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.post("/api/agents", response_model=AgentResponse)
async def create_new_agent(agent: AgentCreate):
    """Create a new agent"""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agents (name, description, system_prompt, voice, vad_threshold,
                              silence_duration_ms, prefix_padding_ms, voice_enabled, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (agent.name, agent.description, agent.system_prompt, agent.voice,
              agent.vad_threshold, agent.silence_duration_ms, agent.prefix_padding_ms,
              1 if agent.voice_enabled else 0, now, now))
        conn.commit()
        agent_id = cursor.lastrowid
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        return dict(cursor.fetchone())


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_single_agent(agent_id: int):
    """Get a single agent by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ? AND is_active = 1", (agent_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        return dict(row)


@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
async def update_existing_agent(agent_id: int, agent: AgentUpdate):
    """Update an existing agent"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ? AND is_active = 1", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        updates = []
        values = []
        for field, value in agent.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.utcnow().isoformat())
            values.append(agent_id)
            cursor.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        return dict(cursor.fetchone())


@app.delete("/api/agents/{agent_id}")
async def disable_agent(agent_id: int):
    """Disable an agent (soft delete)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ? AND is_active = 1", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        cursor.execute("UPDATE agents SET is_active = 0, updated_at = ? WHERE id = ?",
                      (datetime.utcnow().isoformat(), agent_id))
        conn.commit()
        return {"message": "Agent disabled successfully"}


# ============ PRODUCT CRUD ENDPOINTS ============

@app.get("/api/products", response_model=List[ProductResponse])
async def list_all_products():
    """Get all active products"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.post("/api/products", response_model=ProductResponse)
async def create_new_product(product: ProductCreate):
    """Create a new product"""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, price, description, url, image_url, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (product.name, product.price, product.description, product.url, product.image_url, now, now))
        conn.commit()
        product_id = cursor.lastrowid
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return dict(cursor.fetchone())


@app.get("/api/products/{product_id}", response_model=ProductResponse)
async def get_single_product(product_id: int):
    """Get a single product by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ? AND is_active = 1", (product_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return dict(row)


@app.put("/api/products/{product_id}", response_model=ProductResponse)
async def update_existing_product(product_id: int, product: ProductUpdate):
    """Update an existing product"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ? AND is_active = 1", (product_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")

        updates = []
        values = []
        for field, value in product.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.utcnow().isoformat())
            values.append(product_id)
            cursor.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return dict(cursor.fetchone())


@app.delete("/api/products/{product_id}")
async def disable_product(product_id: int):
    """Disable a product (soft delete)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ? AND is_active = 1", (product_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")

        cursor.execute("UPDATE products SET is_active = 0, updated_at = ? WHERE id = ?",
                      (datetime.utcnow().isoformat(), product_id))
        conn.commit()
        return {"message": "Product disabled successfully"}


# ============ TOOL CRUD ENDPOINTS ============

@app.get("/api/tools", response_model=List[ToolResponse])
async def list_all_tools():
    """Get all active tools"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tools WHERE is_active = 1 ORDER BY name")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.post("/api/tools", response_model=ToolResponse)
async def create_new_tool(tool: ToolCreate):
    """Create a new tool"""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tools (name, description, parameters, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (tool.name, tool.description, tool.parameters, now, now))
        conn.commit()
        tool_id = cursor.lastrowid
        cursor.execute("SELECT * FROM tools WHERE id = ?", (tool_id,))
        return dict(cursor.fetchone())


@app.get("/api/tools/{tool_id}", response_model=ToolResponse)
async def get_single_tool(tool_id: int):
    """Get a single tool by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tools WHERE id = ? AND is_active = 1", (tool_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tool not found")
        return dict(row)


@app.put("/api/tools/{tool_id}", response_model=ToolResponse)
async def update_existing_tool(tool_id: int, tool: ToolUpdate):
    """Update an existing tool"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tools WHERE id = ? AND is_active = 1", (tool_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Tool not found")

        updates = []
        values = []
        for field, value in tool.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.utcnow().isoformat())
            values.append(tool_id)
            cursor.execute(f"UPDATE tools SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

        cursor.execute("SELECT * FROM tools WHERE id = ?", (tool_id,))
        return dict(cursor.fetchone())


@app.delete("/api/tools/{tool_id}")
async def disable_tool(tool_id: int):
    """Disable a tool (soft delete)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tools WHERE id = ? AND is_active = 1", (tool_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Tool not found")

        cursor.execute("UPDATE tools SET is_active = 0, updated_at = ? WHERE id = ?",
                      (datetime.utcnow().isoformat(), tool_id))
        conn.commit()
        return {"message": "Tool disabled successfully"}


# ============ AGENT-TOOL ASSIGNMENT ENDPOINTS ============

@app.get("/api/agents/{agent_id}/tools", response_model=List[ToolResponse])
async def get_agent_tools(agent_id: int):
    """Get tools assigned to an agent"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ? AND is_active = 1", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        cursor.execute("""
            SELECT t.* FROM tools t
            JOIN agent_tools at ON t.id = at.tool_id
            WHERE at.agent_id = ? AND t.is_active = 1
            ORDER BY t.name
        """, (agent_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.put("/api/agents/{agent_id}/tools")
async def assign_tools_to_agent(agent_id: int, assignment: AgentToolAssign):
    """Assign tools to an agent (replaces existing assignments)"""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ? AND is_active = 1", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        # Remove existing assignments
        cursor.execute("DELETE FROM agent_tools WHERE agent_id = ?", (agent_id,))

        # Add new assignments
        for tool_id in assignment.tool_ids:
            cursor.execute("SELECT id FROM tools WHERE id = ? AND is_active = 1", (tool_id,))
            if cursor.fetchone():
                cursor.execute("""
                    INSERT INTO agent_tools (agent_id, tool_id, created_at)
                    VALUES (?, ?, ?)
                """, (agent_id, tool_id, now))

        conn.commit()
        return {"message": "Tools assigned successfully"}


# ============ REPORT ENDPOINTS ============

@app.get("/api/reports", response_model=List[ReportResponse])
async def list_all_reports():
    """Get all call reports"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM call_reports ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/api/reports/{report_id}", response_model=ReportResponse)
async def get_single_report(report_id: int):
    """Get a single report by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM call_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        return dict(row)


@app.post("/api/reports/generate", response_model=ReportResponse)
async def generate_call_report(req: ReportGenerateRequest):
    """Generate a post-call coaching report using GPT-4"""
    import json as json_module

    # Get agent name if agent_id provided
    agent_name = "Unknown Agent"
    if req.agent_id:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM agents WHERE id = ?", (req.agent_id,))
            row = cursor.fetchone()
            if row:
                agent_name = row["name"]

    # Format conversation for GPT
    conversation_text = ""
    for turn in req.conversation:
        role = turn.get("role", "unknown")
        text = turn.get("text", "")
        if role == "user":
            conversation_text += f"Salesperson/Customer: {text}\n"
        elif role == "ai":
            conversation_text += f"AI Coach suggested: {text}\n"
        elif role == "tool":
            conversation_text += f"[Product recommended: {text}]\n"

    # Call GPT-4 for analysis
    analysis_prompt = f"""Analyze this sales call conversation and provide coaching feedback.

Call Duration: {req.duration_seconds // 60} minutes {req.duration_seconds % 60} seconds

Conversation:
{conversation_text}

Provide your analysis in the following JSON format:
{{
    "summary": "2-3 sentence summary of the call",
    "highlights": ["point 1 of what went well", "point 2", ...],
    "coaching_tips": ["specific improvement suggestion 1", "suggestion 2", ...]
}}

Focus on actionable coaching tips. Be encouraging but honest."""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "You are a sales coaching expert. Analyze calls and provide actionable feedback."},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"}
                },
                timeout=30.0
            )
            data = response.json()
            analysis = json_module.loads(data["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"GPT analysis error: {e}")
        analysis = {
            "summary": "Unable to generate analysis",
            "highlights": [],
            "coaching_tips": []
        }

    # Save to database
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO call_reports (agent_id, agent_name, conversation, summary, coaching_tips, highlights, duration_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.agent_id,
            agent_name,
            json_module.dumps(req.conversation),
            analysis.get("summary", ""),
            json_module.dumps(analysis.get("coaching_tips", [])),
            json_module.dumps(analysis.get("highlights", [])),
            req.duration_seconds,
            now
        ))
        conn.commit()
        report_id = cursor.lastrowid
        cursor.execute("SELECT * FROM call_reports WHERE id = ?", (report_id,))
        return dict(cursor.fetchone())


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: int):
    """Delete a report"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM call_reports WHERE id = ?", (report_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Report not found")
        cursor.execute("DELETE FROM call_reports WHERE id = ?", (report_id,))
        conn.commit()
        return {"message": "Report deleted successfully"}


# ============ TOKEN & SCREENSHOT ENDPOINTS ============

@app.post("/api/token")
async def get_realtime_session_token(req: TokenRequest):
    """Get ephemeral token for direct frontend connection to OpenAI Realtime API (Beta)"""
    import json as json_module

    # Default config
    instructions = SALES_PROMPT
    voice = "alloy"
    vad_threshold = 0.6
    silence_duration_ms = 800
    prefix_padding_ms = 300
    voice_enabled = True  # Default to voice enabled
    agent_tools = []

    # Load from agent if agent_id provided
    if req.agent_id:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents WHERE id = ? AND is_active = 1", (req.agent_id,))
            agent = cursor.fetchone()
            if agent:
                agent = dict(agent)
                instructions = agent["system_prompt"]
                voice = agent["voice"]
                vad_threshold = agent["vad_threshold"]
                silence_duration_ms = agent["silence_duration_ms"]
                prefix_padding_ms = agent["prefix_padding_ms"]
                voice_enabled = bool(agent.get("voice_enabled", 1))

            # Fetch tools assigned to this agent
            cursor.execute("""
                SELECT t.* FROM tools t
                JOIN agent_tools at ON t.id = at.tool_id
                WHERE at.agent_id = ? AND t.is_active = 1
            """, (req.agent_id,))
            agent_tools = [dict(row) for row in cursor.fetchall()]
    elif req.prompt:
        # Backward compatibility: use custom prompt if provided
        instructions = req.prompt

    # UI override for voice_enabled
    if req.voice_enabled is not None:
        voice_enabled = req.voice_enabled

    # Fetch products and append to instructions
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
        products = [dict(row) for row in cursor.fetchall()]

    if products:
        product_lines = []
        for p in products:
            price_str = f"${p['price']}" if p['price'] else "Contact for pricing"
            desc_str = f" - {p['description']}" if p['description'] else ""
            product_lines.append(f"- ID:{p['id']} {p['name']} ({price_str}){desc_str}")

        product_context = "\n\nPRODUCT CATALOG (use product IDs when calling tools):\n" + "\n".join(product_lines)
        instructions = instructions + product_context

    # Add highlight tool instructions
    highlight_instructions = """

IMPORTANT - VISUAL HIGHLIGHTING:
When you mention specific details like prices, features, or product names that are visible on the user's screen, USE the highlight_ui_element tool to visually highlight that text. This creates a powerful sync between what you say and what the user sees.

CRITICAL: When highlighting prices, use ONLY the number without currency symbols (₹, $, etc.) because the product cards show just the number.

Examples:
- Price "19.99 lakh" → call highlight_ui_element(text_to_find="19.99")
- Product "Kia Seltos" → call highlight_ui_element(text_to_find="Kia Seltos")
- Feature "Sunroof" → call highlight_ui_element(text_to_find="Sunroof")

Always highlight key details as you mention them to draw the user's attention."""
    instructions = instructions + highlight_instructions

    # Set modalities based on voice_enabled
    modalities = ["text", "audio"] if voice_enabled else ["text"]

    # Format tools for OpenAI Realtime API
    openai_tools = []
    for tool in agent_tools:
        openai_tools.append({
            "type": "function",
            "name": tool["name"],
            "description": tool["description"] or "",
            "parameters": json_module.loads(tool["parameters"]) if tool["parameters"] else {"type": "object", "properties": {}}
        })

    # Built-in tool: highlight_ui_element for visual sync between voice and UI
    openai_tools.append({
        "type": "function",
        "name": "highlight_ui_element",
        "description": "Visually highlight text on screen when talking about it to draw user attention. Use this when mentioning specific features, prices, or product details visible on the product card.",
        "parameters": {
            "type": "object",
            "properties": {
                "text_to_find": {
                    "type": "string",
                    "description": "The exact text or short phrase to highlight (e.g. '24/7 Support', '$99', 'Premium Plan')"
                }
            },
            "required": ["text_to_find"]
        }
    })

    # Build session config for GA Realtime API
    session_config = {
        "model": "gpt-realtime",
        "modalities": modalities,
        "instructions": instructions,
        "voice": voice,
        "input_audio_transcription": {"model": "whisper-1"},
        "turn_detection": {
            "type": "server_vad",
            "threshold": vad_threshold,
            "prefix_padding_ms": prefix_padding_ms,
            "silence_duration_ms": silence_duration_ms
        }
    }

    # Add tools if any are assigned
    if openai_tools:
        session_config["tools"] = openai_tools

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1"
            },
            json=session_config
        )
        return response.json()


@app.post("/api/analyze-screenshot")
async def analyze_screenshot_with_vision(req: ScreenshotAnalysisRequest):
    """Analyze screenshot using GPT-4o Vision for sales context"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "Describe this sales call screen in 1 sentence. Focus on: what's shown, pricing visible, objections, opportunities."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{req.image}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 100
            },
            timeout=10.0
        )
        data = response.json()
        return {"context": data["choices"][0]["message"]["content"]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
