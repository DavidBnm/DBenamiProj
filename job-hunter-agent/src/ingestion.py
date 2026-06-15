import requests
from bs4 import BeautifulSoup
import re
import time
import random
import logging
from typing import List, Dict, Optional
from config import SCRAPE_PAGES_LIMIT
from src.database import is_job_processed, save_raw_job

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# List of realistic user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

# Robust mock data for testing and fallback
MOCK_JOBS = [
    {
        "job_id": "mock-de-001",
        "title": "Data Engineer - Modern Data Stack",
        "company": "Riskified",
        "location": "Tel Aviv-Yafo, Israel",
        "link": "https://www.linkedin.com/jobs/view/mock-de-001",
        "description": (
            "We are looking for a Data Engineer to join our growing data team. "
            "Requirements:\n"
            "- 3-4 years of experience as a Data Engineer.\n"
            "- Strong programming skills in Python (Pandas) and SQL.\n"
            "- Hands-on experience with dbt, Airflow, and BigQuery.\n"
            "- Experience with Docker and CI/CD pipelines.\n"
            "- Passion for Modern Data Stack (MDS) and analytics engineering.\n"
            "- Team player with excellent communication skills."
        )
    },
    {
        "job_id": "mock-bi-002",
        "title": "BI Developer / Analytics Engineer",
        "company": "Playtika",
        "location": "Herzliya, Israel",
        "link": "https://www.linkedin.com/jobs/view/mock-bi-002",
        "description": (
            "Playtika is looking for a BI Developer & Analytics Engineer to build state-of-the-art BI dashboards "
            "and robust data pipelines.\n"
            "What you will do:\n"
            "- Maintain and build tables using SQL (MySQL, BigQuery) and dbt.\n"
            "- Schedule tasks using Apache Airflow.\n"
            "- Work closely with product managers to model business logic.\n"
            "Requirements:\n"
            "- 3 years of experience in BI/Analytics engineering.\n"
            "- Strong SQL and Python skills.\n"
            "- Familiarity with dbt and version control (Git).\n"
            "- Experience with Docker is a plus."
        )
    },
    {
        "job_id": "mock-senior-003",
        "title": "Senior Data Engineering Tech Lead",
        "company": "Wix",
        "location": "Tel Aviv, Israel",
        "link": "https://www.linkedin.com/jobs/view/mock-senior-003",
        "description": (
            "We are seeking a Senior Data Engineering Tech Lead to oversee our core data infrastructure.\n"
            "Requirements:\n"
            "- 8+ years of professional experience in Big Data Engineering.\n"
            "- Hands-on leadership / management experience, leading at least 4 engineers.\n"
            "- Expert-level knowledge in Scala/Java and Spark.\n"
            "- Deep understanding of Kafka, Kubernetes, and AWS ecosystem.\n"
            "- Design complex data streaming architectures."
        )
    },
    {
        "job_id": "mock-staff-004",
        "title": "Staff Data Architect",
        "company": "Monday.com",
        "location": "Tel Aviv, Israel",
        "link": "https://www.linkedin.com/jobs/view/mock-staff-004",
        "description": (
            "We are looking for a Staff Data Architect to set the vision for our enterprise data platforms.\n"
            "Qualifications:\n"
            "- 10+ years of experience in data platform engineering.\n"
            "- Proven experience defining company-wide data strategy.\n"
            "- Expertise in Snowflake, dbt, python, Airflow, and Cloud architecture."
        )
    },
    {
        "job_id": "mock-junior-005",
        "title": "Junior Data Analyst / BI",
        "company": "Fiverr",
        "location": "Tel Aviv, Israel",
        "link": "https://www.linkedin.com/jobs/view/mock-junior-005",
        "description": (
            "Entry-level position for a Junior Analyst to learn and grow.\n"
            "Requirements:\n"
            "- 0-1 years of experience with SQL and Excel.\n"
            "- Strong analytical mindset.\n"
            "- No prior professional Python experience required, but basic SQL is a must."
        )
    }
]

def get_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }

def extract_job_id(url: str) -> Optional[str]:
    """Extracts job ID from public LinkedIn URL."""
    # Matches patterns like /jobs/view/data-engineer-at-riskified-3746592837/
    # or /jobs/view/3746592837/
    match = re.search(r"/view/.*?(\d+)", url)
    if match:
        return match.group(1)
    
    # Check for currentJobId param
    match = re.search(r"currentJobId=(\d+)", url)
    if match:
        return match.group(1)
    
    return None

def fetch_job_description(job_id: str) -> Optional[str]:
    """Fetches full job description text using public API endpoint."""
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    logger.info(f"Fetching job description for ID: {job_id}")
    
    try:
        response = requests.get(url, headers=get_headers(), timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch job description (HTTP {response.status_code}) for ID {job_id}")
            return None
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Selectors for description
        desc_div = (
            soup.find("div", class_="description__text")
            or soup.find("div", class_="show-more-less-html__markup")
            or soup.find("section", class_="description")
        )
        
        if desc_div:
            # Clean up text formatting
            return desc_div.get_text(separator="\n").strip()
            
        return soup.get_text(separator="\n").strip()
    except Exception as e:
        logger.error(f"Error fetching description for {job_id}: {e}")
        return None

def scrape_linkedin_jobs(keyword: str, pages_limit: int = 1) -> List[Dict]:
    """Scrapes LinkedIn's public guest search endpoint for Israel."""
    jobs = []
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    
    for page in range(pages_limit):
        start = page * 25
        params = {
            "keywords": keyword,
            "location": "Israel",
            "start": start
        }
        logger.info(f"Scraping '{keyword}' in Israel - Page {page + 1} (start={start})...")
        
        try:
            response = requests.get(base_url, headers=get_headers(), params=params, timeout=15)
            
            # LinkedIn returns 400 or 429 when rate-limited or at page limit
            if response.status_code != 200:
                logger.warning(f"LinkedIn returned status code {response.status_code} for search '{keyword}'")
                break
                
            soup = BeautifulSoup(response.content, "html.parser")
            cards = soup.find_all("li")
            
            if not cards:
                logger.info("No jobs found on this page.")
                break
                
            for card in cards:
                link_tag = (
                    card.find("a", class_="base-card__full-link")
                    or card.find("a", class_="base-search-card__title-link")
                )
                if not link_tag or not link_tag.get("href"):
                    continue
                    
                href = link_tag.get("href").split("?")[0] # Clean query params
                job_id = extract_job_id(href)
                if not job_id:
                    continue
                    
                title_tag = card.find("h3", class_="base-search-card__title")
                title = title_tag.get_text().strip() if title_tag else "Unknown Title"
                
                company_tag = card.find("h4", class_="base-search-card__subtitle") or card.find("a", class_="hidden-nested-link")
                company = company_tag.get_text().strip() if company_tag else "Unknown Company"
                
                location_tag = card.find("span", class_="job-search-card__location")
                location = location_tag.get_text().strip() if location_tag else "Israel"
                
                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "link": href
                })
                
            # Nice gentle delay between page requests
            time.sleep(random.uniform(2.0, 4.0))
            
        except Exception as e:
            logger.error(f"Error scraping page {page} for keyword {keyword}: {e}")
            break
            
    return jobs

def ingest_jobs(use_fallback: bool = True) -> int:
    """
    Orchestrates the ingestion layer.
    Scrapes LinkedIn public search and detail endpoints.
    If scraper gets rate-limited/blocked, optionally falls back to loading robust Mock Data.
    Saves newly discovered jobs into the database.
    """
    keywords = ["Data Engineer", "BI Developer", "Analytics Engineer"]
    new_jobs_count = 0
    scraped_jobs = []
    
    # 1. Scraping Live Data
    for kw in keywords:
        logger.info(f"Starting ingestion process for keyword: {kw}")
        found = scrape_linkedin_jobs(kw, pages_limit=SCRAPE_PAGES_LIMIT)
        scraped_jobs.extend(found)
        # Sleep between keywords
        time.sleep(random.uniform(2.0, 5.0))
        
    logger.info(f"Live scraper found {len(scraped_jobs)} unique listings.")
    
    # 2. Saving to database and fetching full description
    for job in scraped_jobs:
        job_id = job["job_id"]
        if is_job_processed(job_id):
            continue
            
        # Introduce a sleep before details call
        time.sleep(random.uniform(1.5, 3.5))
        
        description = fetch_job_description(job_id)
        if description:
            saved = save_raw_job(
                job_id=job_id,
                title=job["title"],
                company=job["company"],
                link=job["link"],
                description=description
            )
            if saved:
                new_jobs_count += 1
                logger.info(f"Ingested live job: {job['title']} at {job['company']}")
        else:
            logger.warning(f"Could not fetch description for {job_id}, skipping for now.")
            
    # 3. Fallback to mock data if no new jobs were ingested (e.g. rate limited or in localized testing environments)
    if new_jobs_count == 0 and use_fallback:
        logger.info("No new live jobs ingested (potentially rate-limited). Loading mock jobs for verification/testing.")
        for mock_job in MOCK_JOBS:
            job_id = mock_job["job_id"]
            if not is_job_processed(job_id):
                saved = save_raw_job(
                    job_id=job_id,
                    title=mock_job["title"],
                    company=mock_job["company"],
                    link=mock_job["link"],
                    description=mock_job["description"]
                )
                if saved:
                    new_jobs_count += 1
                    logger.info(f"Ingested mock job: {mock_job['title']} at {mock_job['company']}")
                    
    return new_jobs_count

if __name__ == "__main__":
    from src.database import init_db
    init_db()
    ingested = ingest_jobs(use_fallback=True)
    print(f"Total new jobs ingested: {ingested}")
