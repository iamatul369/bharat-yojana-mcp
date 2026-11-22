import os
import requests
from io import BytesIO
from pypdf import PdfReader
from supabase import create_client
from google import genai

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
ai_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
DATAGOV_API_KEY = os.environ.get("DATAGOV_API_KEY", "")

PDF_SOURCES = [
    {
        "scheme_code": "SISFS",
        "scheme_name": "Startup India Seed Fund Scheme",
        "target_group": "Business",
        "url": "https://startupindia.gov.in"
    },
    {
        "scheme_code": "PMEGP",
        "scheme_name": "Prime Minister Employment Generation Programme",
        "target_group": "Business",
        "url": "https://kviconline.gov.in"
    },
    {
        "scheme_code": "PM-USP",
        "scheme_name": "PM Uchchatar Shiksha Protsahan (Central Sector Scholarship)",
        "target_group": "Student",
        "url": "https://scholarships.gov.in"
    }
]


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if len(c) > 100]


def get_embedding(text: str) -> list[float]:
    res = ai_client.models.embed_content(model="text-embedding-004", contents=text)
    return res.embeddings[0].values


def sync_official_pdfs():
    for src in PDF_SOURCES:
        try:
            resp = requests.get(src["url"], timeout=25, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            if resp.status_code != 200:
                print(f"Skipping {src['scheme_code']}: HTTP {resp.status_code}")
                continue

            reader = PdfReader(BytesIO(resp.content))
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            chunks = chunk_text(full_text)[:40]

            supabase.table("central_scheme_docs").delete().eq("scheme_code", src["scheme_code"]).execute()
            for chunk in chunks:
                emb = get_embedding(f"{src['scheme_name']} ({src['target_group']}): {chunk}")
                supabase.table("central_scheme_docs").insert({
                    "scheme_code": src["scheme_code"],
                    "scheme_name": src["scheme_name"],
                    "target_group": src["target_group"],
                    "source_pdf_url": src["url"],
                    "chunk_text": chunk,
                    "embedding": emb
                }).execute()
            print(f"Synced {len(chunks)} chunks for {src['scheme_name']}")
        except Exception as e:
            print(f"Error syncing {src['scheme_code']}: {e}")


def sync_datagov_catalog():
    core_schemes = [
        {
            "scheme_code": "SISFS",
            "scheme_name": "Startup India Seed Fund Scheme",
            "ministry": "Ministry of Commerce & Industry (DPIIT)",
            "target_group": "Business",
            "benefit_type": "Grant & Debt",
            "max_benefit_inr": "Up to Rs 20 Lakh (Grant) / Rs 50 Lakh (Debt/Convertible)",
            "income_or_turnover_limit": "DPIIT-recognized startup incorporated < 2 years ago",
            "official_url": "https://startupindia.gov.in"
        },
        {
            "scheme_code": "PMEGP",
            "scheme_name": "Prime Minister Employment Generation Programme",
            "ministry": "Ministry of MSME",
            "target_group": "Business",
            "benefit_type": "Subsidy",
            "max_benefit_inr": "15% to 35% margin money subsidy on projects up to Rs 50 Lakh (Manufacturing) / Rs 20 Lakh (Service)",
            "income_or_turnover_limit": "Any individual above 18 years setting up a new micro-enterprise",
            "official_url": "https://kviconline.gov.in"
        },
        {
            "scheme_code": "PM-USP-CSSS",
            "scheme_name": "Central Sector Scheme of Scholarship for College & University Students",
            "ministry": "Ministry of Education",
            "target_group": "Student",
            "benefit_type": "Scholarship",
            "max_benefit_inr": "Rs 12,000/year (UG) to Rs 20,000/year (PG)",
            "income_or_turnover_limit": "Family income <= Rs 4.5 Lakh/year & >80th percentile in Class 12",
            "official_url": "https://scholarships.gov.in"
        },
        {
            "scheme_code": "AICTE-PRAGATI",
            "scheme_name": "Pragati Scholarship Scheme for Girl Students (Technical Education)",
            "ministry": "Ministry of Education (AICTE)",
            "target_group": "Student",
            "benefit_type": "Scholarship",
            "max_benefit_inr": "Rs 50,000 per annum for every year of study",
            "income_or_turnover_limit": "Family income <= Rs 8 Lakh/year; admitted to 1st year AICTE diploma/degree",
            "official_url": "https://scholarships.gov.in"
        },
        {
            "scheme_code": "PM-SURYA-GHAR",
            "scheme_name": "PM Surya Ghar: Muft Bijli Yojana",
            "ministry": "Ministry of New and Renewable Energy",
            "target_group": "Citizen",
            "benefit_type": "Subsidy",
            "max_benefit_inr": "Up to Rs 78,000 subsidy for 3kW+ rooftop solar",
            "income_or_turnover_limit": "Any Indian residential household with valid electricity connection",
            "official_url": "https://pmsuryaghar.gov.in"
        },
        {
            "scheme_code": "PM-VISHWAKARMA",
            "scheme_name": "PM Vishwakarma Scheme for Artisans & Craftspeople",
            "ministry": "Ministry of MSME",
            "target_group": "Citizen",
            "benefit_type": "Loan & Skill Grant",
            "max_benefit_inr": "Rs 15,000 toolkit grant + collateral-free loan up to Rs 3 Lakh at 5% interest",
            "income_or_turnover_limit": "Traditional artisans across 18 designated trades aged 18+",
            "official_url": "https://pmvishwakarma.gov.in"
        }
    ]

    if DATAGOV_API_KEY and os.environ.get("DATAGOV_RESOURCE_ID"):
        resource_id = os.environ["DATAGOV_RESOURCE_ID"]
        api_url = f"https://data.gov.in{resource_id}?api-key={DATAGOV_API_KEY}&format=json&limit=100"
        data = requests.get(api_url, timeout=20).json()
        for rec in data.get("records", []):
            core_schemes.append({
                "scheme_code": rec.get("scheme_code", rec.get("scheme_name", "")[:20]),
                "scheme_name": rec.get("scheme_name", "Unknown Scheme"),
                "ministry": rec.get("ministry", "Government of India"),
                "target_group": rec.get("category", "Citizen"),
                "benefit_type": rec.get("benefit_type", "Financial Assistance"),
                "max_benefit_inr": rec.get("benefit_amount", "As per norms"),
                "income_or_turnover_limit": rec.get("eligibility", "Check official portal"),
                "official_url": rec.get("url", "https://myscheme.gov.in")
            })

    supabase.table("central_schemes").upsert(core_schemes, on_conflict="scheme_code").execute()
    print(f"Upserted {len(core_schemes)} structured central schemes.")


if __name__ == "__main__":
    sync_datagov_catalog()
    sync_official_pdfs()
