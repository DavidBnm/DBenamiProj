import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"  # Highly performant and cost-effective for structured JSON

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Scraper Settings
SCRAPE_PAGES_LIMIT = int(os.getenv("SCRAPE_PAGES_LIMIT", 3))
MIN_SCORE_THRESHOLD = int(os.getenv("MIN_SCORE_THRESHOLD", 8))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "jobs.db"))

# Candidate Profile
CANDIDATE_PROFILE = (
    "Data Engineer & BI Developer with 3 to 4 years of professional experience (Mid-Level / Mid-Senior). "
    "Core Stack: Python (Pandas, PySpark), SQL (BigQuery, MySQL), dbt, Airflow, Docker, "
    "with a heavy preference for Modern Data Stack (MDS) and analytics engineering."
)

# Scoring/Filtering prompt instructions
CRITICAL_FILTERING_RULE = (
    "The candidate has 3-4 years of experience. Filter OUT or give a very low score (1 to 3) to strict "
    "Senior, Staff, Lead, or Principal positions that explicitly demand 7+ years of experience or management/team lead responsibilities. "
    "Focus heavily on roles looking for 3-5 years of experience."
)
