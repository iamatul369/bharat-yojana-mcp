import os
import requests
from io import BytesIO
from pypdf import PdfReader
from supabase import create_client
from google import genai
from google.genai import types

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
    res = ai_client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return res.embeddings.values


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
        # --- BUSINESS & STARTUP SCHEMES ---
        {
            "scheme_code": "SISFS",
            "scheme_name": "Startup India Seed Fund Scheme (SISFS)",
            "ministry": "Ministry of Commerce & Industry (DPIIT)",
            "target_group": "Business",
            "benefit_type": "Grant & Debt",
            "max_benefit_inr": "Up to Rs 20 Lakh (Grant for PoC/Prototype) + up to Rs 50 Lakh (Convertible Debentures/Debt)",
            "income_or_turnover_limit": "DPIIT-recognized startup incorporated less than 2 years ago; not received >Rs 10L from other govt schemes",
            "official_url": "https://startupindia.gov.in"
        },
        {
            "scheme_code": "PMEGP",
            "scheme_name": "Prime Minister's Employment Generation Programme (PMEGP)",
            "ministry": "Ministry of MSME",
            "target_group": "Business",
            "benefit_type": "Subsidy",
            "max_benefit_inr": "15% to 35% subsidy on project cost up to Rs 50 Lakh (Manufacturing) and Rs 20 Lakh (Service)",
            "income_or_turnover_limit": "Any individual aged 18+ setting up a new micro-enterprise (higher 25%-35% subsidy in rural areas & SC/ST/Women/OBC)",
            "official_url": "https://kviconline.gov.in"
        },
        {
            "scheme_code": "CGTMSE",
            "scheme_name": "Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)",
            "ministry": "Ministry of MSME & SIDBI",
            "target_group": "Business",
            "benefit_type": "Loan Guarantee",
            "max_benefit_inr": "Collateral-free business loans up to Rs 5 Crore with up to 85% credit guarantee coverage",
            "income_or_turnover_limit": "New or existing Udyam-registered Micro and Small Enterprises (manufacturing & service)",
            "official_url": "https://cgtmse.in"
        },
        {
            "scheme_code": "PM-MUDRA",
            "scheme_name": "Pradhan Mantri Mudra Yojana (PMMY) - Shishu, Kishore, Tarun & Tarun Plus",
            "ministry": "Ministry of Finance",
            "target_group": "Business",
            "benefit_type": "Loan",
            "max_benefit_inr": "Collateral-free micro-business loans up to Rs 20 Lakh (Tarun Plus for repeat borrowers)",
            "income_or_turnover_limit": "Non-corporate, non-farm small/micro enterprises, shopkeepers, traders, and service providers",
            "official_url": "https://mudra.org.in"
        },
        {
            "scheme_code": "STANDUP-INDIA",
            "scheme_name": "Stand-Up India Scheme",
            "ministry": "Ministry of Finance",
            "target_group": "Business",
            "benefit_type": "Loan",
            "max_benefit_inr": "Composite bank loan between Rs 10 Lakh and Rs 1 Crore for greenfield enterprises",
            "income_or_turnover_limit": "At least one SC/ST or Woman entrepreneur aged 18+ holding >=51% stake in a new greenfield business",
            "official_url": "https://standupmitra.in"
        },
        {
            "scheme_code": "MSME-CHAMPIONS",
            "scheme_name": "MSME Innovative Scheme (Incubation, Design & IPR)",
            "ministry": "Ministry of MSME",
            "target_group": "Business",
            "benefit_type": "Grant",
            "max_benefit_inr": "Up to Rs 15 Lakh per idea for prototype + up to Rs 1 Lakh to Rs 5 Lakh reimbursement for Patent/Trademark registration",
            "income_or_turnover_limit": "Udyam-registered MSMEs and student innovators",
            "official_url": "https://msme.gov.in"
        },

        # --- STUDENT SCHEMES ---
        {
            "scheme_code": "PM-USP-CSSS",
            "scheme_name": "PM-USP Central Sector Scheme of Scholarship for College & University Students",
            "ministry": "Ministry of Education",
            "target_group": "Student",
            "benefit_type": "Scholarship",
            "max_benefit_inr": "Rs 12,000/year (1st 3 years of UG) and Rs 20,000/year (4th/5th year & PG)",
            "income_or_turnover_limit": "Gross parental income <= Rs 4.5 Lakh/year and above 80th percentile in Class 12 board exam",
            "official_url": "https://scholarships.gov.in"
        },
        {
            "scheme_code": "AICTE-PRAGATI",
            "scheme_name": "AICTE Pragati Scholarship Scheme for Girl Students",
            "ministry": "Ministry of Education (AICTE)",
            "target_group": "Student",
            "benefit_type": "Scholarship",
            "max_benefit_inr": "Rs 50,000 per annum for every year of study (up to 4 years)",
            "income_or_turnover_limit": "Up to 2 girl children per family; annual family income <= Rs 8 Lakh; admitted to 1st year AICTE technical degree/diploma",
            "official_url": "https://scholarships.gov.in"
        },
        {
            "scheme_code": "AICTE-SAKSHAM",
            "scheme_name": "AICTE Saksham Scholarship for Specially-Abled Students",
            "ministry": "Ministry of Education (AICTE)",
            "target_group": "Student",
            "benefit_type": "Scholarship",
            "max_benefit_inr": "Rs 50,000 per annum for tuition and incidental expenses",
            "income_or_turnover_limit": "Students with >=40% disability and family income <= Rs 8 Lakh/year in AICTE-approved technical courses",
            "official_url": "https://scholarships.gov.in"
        },
        {
            "scheme_code": "PM-VIDYALAXMI",
            "scheme_name": "PM-Vidyalaxmi Scheme (Collateral-Free Education Loan & Interest Subvention)",
            "ministry": "Ministry of Education",
            "target_group": "Student",
            "benefit_type": "Loan & Subsidy",
            "max_benefit_inr": "Collateral-free, guarantor-free education loan + 3% interest subvention on loans up to Rs 10 Lakh (100% subvention for income <= Rs 4.5L)",
            "income_or_turnover_limit": "Students admitted to top 860 Quality Higher Educational Institutions (QHEIs); 3% subvention for family income <= Rs 8 Lakh/year",
            "official_url": "https://pmvidyalaxmi.co.in"
        },
        {
            "scheme_code": "NSP-MCM",
            "scheme_name": "Merit-cum-Means Scholarship for Professional & Technical Courses (Minorities)",
            "ministry": "Ministry of Minority Affairs",
            "target_group": "Student",
            "benefit_type": "Scholarship",
            "max_benefit_inr": "Rs 20,000/year course fee reimbursement + Rs 10,000/year (Hosteller) or Rs 5,000/year (Day Scholar) maintenance allowance",
            "income_or_turnover_limit": "Notified minority students with >=50% marks in previous exam and annual family income <= Rs 2.5 Lakh",
            "official_url": "https://scholarships.gov.in"
        },
        {
            "scheme_code": "PM-INTERNSHIP",
            "scheme_name": "Prime Minister's Internship Scheme (Top 500 Companies)",
            "ministry": "Ministry of Corporate Affairs",
            "target_group": "Student",
            "benefit_type": "Stipend & Grant",
            "max_benefit_inr": "Rs 5,000/month stipend for 12 months + Rs 6,000 one-time joining grant",
            "income_or_turnover_limit": "Youth aged 21-24 years (Class 10, 12, ITI, Diploma, or non-IIT/IIM Graduate) not in full-time employment; family income <= Rs 8 Lakh",
            "official_url": "mca.gov.in"
            },
            # --- CITIZEN SCHEMES ---
            {
            "scheme_code": "PM-SURYA-GHAR",
            "scheme_name": "PM Surya Ghar: Muft Bijli Yojana",
            "ministry": "Ministry of New and Renewable Energy",
            "target_group": "Citizen",
            "benefit_type": "Subsidy",
            "max_benefit_inr": "Rs 30,000 for 1kW, Rs 60,000 for 2kW, and Rs 78,000 subsidy for 3kW or higher rooftop solar",
            "income_or_turnover_limit": "Any Indian residential household owning a house with a valid electricity connection",
            "official_url": "https://pmsuryaghar.gov.in"
            },
            {
            "scheme_code": "PM-VISHWAKARMA",
            "scheme_name": "PM Vishwakarma Scheme for Traditional Artisans",
            "ministry": "Ministry of MSME",
            "target_group": "Citizen",
            "benefit_type": "Loan & Grant",
            "max_benefit_inr": "Rs 15,000 toolkit e-voucher + Rs 500/day training stipend + up to Rs 3 Lakh collateral-free loan at 5% interest",
            "income_or_turnover_limit": "Self-employed artisans across 18 traditional trades (carpenter, goldsmith, potter, tailor, etc.) aged 18+",
            "official_url": "https://pmvishwakarma.gov.in"
            },
            {
            "scheme_code": "AB-PMJAY",
            "scheme_name": "Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (AB-PMJAY)",
            "ministry": "Ministry of Health & Family Welfare",
            "target_group": "Citizen",
            "benefit_type": "Insurance",
            "max_benefit_inr": "Rs 5 Lakh per family per year cashless hospitalization cover (plus separate Rs 5 Lakh cover for all senior citizens aged 70+)",
            "income_or_turnover_limit": "Eligible SECC families, frontline health workers, and ALL senior citizens aged 70+ regardless of income",
            "official_url": "nha.gov.in"
            },
            {
            "scheme_code": "PMAY-URBAN-2",
            "scheme_name": "Pradhan Mantri Awas Yojana - Urban 2.0 (Interest Subsidy Scheme)",
            "ministry": "Ministry of Housing & Urban Affairs",
            "target_group": "Citizen",
            "benefit_type": "Subsidy",
            "max_benefit_inr": "Up to Rs 1.80 Lakh interest subsidy on home loans up to Rs 25 Lakh (for houses valued up to Rs 35 Lakh)",
            "income_or_turnover_limit": "EWS (income <= Rs 3L), LIG (<= Rs 6L), and MIG (<= Rs 9L) urban families owning no pucca house anywhere in India",
            "official_url": "https://pmaymis.gov.in"
            },
            {
            "scheme_code": "APY",
            "scheme_name": "Atal Pension Yojana (APY)",
            "ministry": "Ministry of Finance (PFRDA)",
            "target_group": "Citizen",
            "benefit_type": "Pension",
            "max_benefit_inr": "Guaranteed minimum monthly pension of Rs 1,000 to Rs 5,000/month after age 60 (transferred to spouse after death)",
            "income_or_turnover_limit": "Any Indian citizen aged 18 to 40 years with a savings bank account who is not an income-tax payer",
            "official_url": "nsdl.co.in"
            },
            {
            "scheme_code": "PM-KISAN",
            "scheme_name": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
            "ministry": "Ministry of Agriculture & Farmers Welfare",
            "target_group": "Citizen",
            "benefit_type": "Direct Cash Transfer",
            "max_benefit_inr": "Rs 6,000 per year directly into bank account in three equal installments of Rs 2,000 every 4 months",
            "income_or_turnover_limit": "All landholding farmer families across India (excluding institutional landholders and income-tax payers)",
            "official_url": "https://pmkisan.gov.in"
            }
            ]
            if DATAGOV_API_KEY and os.environ.get("DATAGOV_RESOURCE_ID"):
            resource_id = os.environ["DATAGOV_RESOURCE_ID"]
            api_url = f"data.gov.in{resource_id}?api-key={DATAGOV_API_KEY}&format=json&limit=100"
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
            "official_url": rec.get("url", "myscheme.gov.in")
            })
            supabase.table("central_schemes").upsert(core_schemes, on_conflict="scheme_code").execute()
            print(f"Upserted {len(core_schemes)} structured central schemes.")
            if name == "main":
            sync_datagov_catalog()
            sync_official_pdfs()
