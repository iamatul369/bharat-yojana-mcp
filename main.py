import os
import time
from collections import defaultdict
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastmcp import FastMCP
from supabase import create_client
from google import genai

SUPABASE_URL = os.environ["SUPABASE_URL"]
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


def discover_schemes_logic(target_group: Optional[str] = None, benefit_type: Optional[str] = None) -> list[dict]:
    q = supabase.table("central_schemes").select("*")
    if target_group:
        q = q.ilike("target_group", f"%{target_group}%")
    if benefit_type:
        q = q.ilike("benefit_type", f"%{benefit_type}%")
    return q.limit(15).execute().data or []


def search_guidelines_logic(question: str, target_group: Optional[str] = None) -> list[dict]:
    emb = ai_client.models.embed_content(model="text-embedding-004", contents=question).embeddings[0].values
    res = supabase.rpc("match_central_docs", {
        "query_embedding": emb,
        "match_count": 4,
        "filter_group": target_group
    }).execute()
    return res.data or []


mcp = FastMCP("Bharat-Central-Schemes-Tracker")

@mcp.tool()
def discover_central_schemes(target_group: Optional[str] = None, benefit_type: Optional[str] = None) -> list[dict]:
    """Find Indian Central Government schemes filtered by target_group ('Student', 'Business', 'Citizen') or benefit_type ('Scholarship', 'Subsidy', 'Grant', 'Loan')."""
    return discover_schemes_logic(target_group, benefit_type)

@mcp.tool()
def search_scheme_guidelines(question: str, target_group: Optional[str] = None) -> list[dict]:
    """Search official Indian ministry PDF guidelines for exact eligibility criteria, subsidy caps, and application rules."""
    return search_guidelines_logic(question, target_group)


mcp_app = mcp.http_app(path="/")
app = FastAPI(
    title="Bharat Central Schemes & Opportunities API",
    description="Discover Indian Central Government schemes, scholarships, startup grants, and subsidies for Students, Businesses, and Citizens.",
    version="1.0.0",
    servers=[{"url": "https://bharat-yojana-mcp.onrender.com"}],
    lifespan=mcp_app.lifespan,
)

app.mount("/mcp", mcp_app)

@app.get("/api/discover", dependencies=[Depends(check_rate_limit), Depends(verify_token)])
def api_discover_schemes(target_group: Optional[str] = None, benefit_type: Optional[str] = None):
    """Discover Central schemes for Students, Businesses, or Citizens."""
    return {"schemes": discover_schemes_logic(target_group, benefit_type)}

@app.get("/api/guidelines", dependencies=[Depends(check_rate_limit), Depends(verify_token)])
def api_search_guidelines(question: str, target_group: Optional[str] = None):
    """Search official ministry PDF rules and eligibility details."""
    return {"guidelines": search_guidelines_logic(question, target_group)}

@app.get("/health")
def health():
    return {"status": "ok"}
