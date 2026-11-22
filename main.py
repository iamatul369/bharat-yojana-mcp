import os
import time
from collections import defaultdict
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from fastmcp import FastMCP
from supabase import create_client
from google import genai
from google.genai import types

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
API_SECRET_TOKEN = os.environ.get("API_SECRET_TOKEN", "bharat-public-2026")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

request_counts = defaultdict(list)
RATE_LIMIT_PER_MIN = 30

def check_rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    request_counts[ip] = [t for t in request_counts[ip] if now - t < 60]
    if len(request_counts[ip]) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in 1 minute.")
    request_counts[ip].append(now)

security = HTTPBearer(auto_error=False)
def verify_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    if API_SECRET_TOKEN and (not creds or creds.credentials != API_SECRET_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid API Key")


def discover_schemes_logic(target_group: str = "", benefit_type: str = "") -> list[dict]:
    """Find Indian Central Government schemes filtered by target_group ('Student', 'Business', 'Citizen') or benefit_type ('Scholarship', 'Subsidy', 'Grant', 'Loan')."""
    q = supabase.table("central_schemes").select("*")
    if target_group:
        q = q.ilike("target_group", f"%{target_group}%")
    if benefit_type:
        q = q.ilike("benefit_type", f"%{benefit_type}%")
    return q.limit(25).execute().data or []


def search_guidelines_logic(question: str, target_group: str = "") -> list[dict]:
    """Search official Indian ministry PDF guidelines for exact eligibility criteria, subsidy caps, and application rules."""
    emb_res = ai_client.models.embed_content(
        model="gemini-embedding-001",
        contents=question,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    emb = emb_res.embeddings[0].values
    res = supabase.rpc("match_central_docs", {
        "query_embedding": emb,
        "match_count": 4,
        "filter_group": target_group if target_group else None
    }).execute()
    return res.data or []


mcp = FastMCP("Bharat-Central-Schemes-Tracker")

@mcp.tool()
def discover_central_schemes(target_group: str = "", benefit_type: str = "") -> list[dict]:
    """Find Indian Central Government schemes filtered by target_group ('Student', 'Business', 'Citizen') or benefit_type ('Scholarship', 'Subsidy', 'Grant', 'Loan')."""
    return discover_schemes_logic(target_group, benefit_type)

@mcp.tool()
def search_scheme_guidelines(question: str, target_group: str = "") -> list[dict]:
    """Search official Indian ministry PDF guidelines for exact eligibility criteria, subsidy caps, and application rules."""
    return search_guidelines_logic(question, target_group)


mcp_app = mcp.http_app(path="/")
app = FastAPI(
    title="Bharat Central Schemes & Opportunities API",
    description="Discover Indian Central Government schemes, scholarships, startup grants, and subsidies.",
    version="1.0.0",
    servers=[{"url": "https://bharat-yojana-mcp.onrender.com"}],
    lifespan=mcp_app.lifespan,
)

app.mount("/mcp", mcp_app)

@app.get("/")
def serve_chat_ui():
    return FileResponse("index.html")

class ChatTurn(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []

SYSTEM_PROMPT = """You are 'Bharat Yojana Sahayak', an expert AI assistant helping Indian citizens, students, and business founders discover Central Government schemes, scholarships, startup grants, and subsidies.
Always call `discover_schemes_logic` and `search_guidelines_logic` to check verified data before answering. Use conversation history to answer follow-up questions accurately. Present clear scheme names, ministries, INR benefit limits, eligibility rules, and clickable official portal URLs."""

@app.post("/chat", dependencies=[Depends(check_rate_limit)])
def public_chat(req: ChatRequest):
    try:
        available = [
            m.name.replace("models/", "")
            for m in ai_client.models.list()
            if "flash" in m.name.lower() and "image" not in m.name.lower() and "audio" not in m.name.lower()
        ]
    except Exception:
        available = []

    candidates = available or ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite"]
    last_err = ""

    conversation = [
        types.Content(role=turn.role, parts=[types.Part.from_text(text=turn.text)])
        for turn in req.history
        if turn.role in ("user", "model")
    ]
    conversation.append(
        types.Content(role="user", parts=[types.Part.from_text(text=req.message)])
    )

    for model_name in candidates[:4]:
        for attempt in range(2):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=conversation,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=[discover_schemes_logic, search_guidelines_logic],
                        temperature=0.2,
                    ),
                )
                return {"reply": response.text or "No matching information found."}
            except Exception as e:
                last_err = f"[{model_name}] {str(e)}"
                if "503" in last_err:
                    time.sleep(1.5)
                    continue
                break
    return {"reply": f"Temporary issue: {last_err}"}

@app.get("/api/discover", dependencies=[Depends(check_rate_limit), Depends(verify_token)])
def api_discover_schemes(target_group: Optional[str] = None, benefit_type: Optional[str] = None):
    return {"schemes": discover_schemes_logic(target_group or "", benefit_type or "")}

@app.get("/api/guidelines", dependencies=[Depends(check_rate_limit), Depends(verify_token)])
def api_search_guidelines(question: str, target_group: Optional[str] = None):
    return {"guidelines": search_guidelines_logic(question, target_group or "")}

@app.get("/health")
def health():
    return {"status": "ok"}
