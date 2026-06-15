import json
import logging
from typing import Dict, Optional
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY, GEMINI_MODEL, CANDIDATE_PROFILE, CRITICAL_FILTERING_RULE
from src.database import update_job_score

logger = logging.getLogger(__name__)

# Pydantic schema for structured output validation
class JobScoringModel(BaseModel):
    match_score: int = Field(..., description="An integer from 1 to 10 rating the job's fit with the candidate's experience and stack.")
    key_technologies: list[str] = Field(..., description="Key technologies, frameworks, and programming languages required by this role.")
    fit_reasons: str = Field(..., description="A 2-3 sentence explanation of the reasoning behind the score, highlighting experience fit and stack compatibility.")
    action_item: str = Field(..., description="A single-sentence direct action item advising the candidate (e.g., 'Apply immediately emphasizing your Airflow and dbt skills' or 'Do not apply: demands 10 years experience').")

def generate_mock_score(title: str, description: str) -> dict:
    """
    Generates a deterministic score based on keywords when GEMINI_API_KEY is not available.
    Useful for local testing and validation checks.
    """
    logger.info("Using keyword-based mock scorer fallback.")
    text = (title + " " + description).lower()
    
    # 1. Experience Check (Critical Filtering Rule)
    is_senior = any(w in text for w in ["senior", "lead", "staff", "architect", "principal", "manager", "head"])
    demands_high_exp = any(w in text for w in ["7 years", "8 years", "10 years", "7+", "8+", "10+"])
    
    # 2. Tech Match Check
    tech_score = 0
    technologies = []
    if "python" in text:
        tech_score += 2
        technologies.append("Python")
    if "dbt" in text:
        tech_score += 2
        technologies.append("dbt")
    if "airflow" in text:
        tech_score += 2
        technologies.append("Airflow")
    if "bigquery" in text or "sql" in text:
        tech_score += 1
        technologies.append("SQL/BigQuery")
    if "docker" in text:
        tech_score += 1
        technologies.append("Docker")
    if "pyspark" in text or "spark" in text:
        tech_score += 1
        technologies.append("PySpark")

    # Calculate final score
    if is_senior or demands_high_exp:
        match_score = max(1, tech_score - 3) # Penalize heavily for senior level
        fit_reasons = (
            f"The job appears to be a senior, lead, or staff role. While it mentions technologies like "
            f"{', '.join(technologies)}, it explicitly calls for senior-level responsibilities or high years of experience, "
            f"which contradicts the candidate's 3-4 years profile."
        )
        action_item = "Skip this position: demands high-level seniority or management responsibilities."
    else:
        match_score = min(10, tech_score + 2) # Base score + 2 for mid level fit
        fit_reasons = (
            f"This matches the mid-level experience requirements. It aligns well with the stack: "
            f"{', '.join(technologies)}. The requirements align with your 3-4 years experience range."
        )
        action_item = "Apply immediately highlighting your core data engineering capabilities."

    return {
        "match_score": match_score,
        "key_technologies": technologies,
        "fit_reasons": fit_reasons,
        "action_item": action_item
    }

def score_job(job_id: str, title: str, company: str, description: str) -> Optional[dict]:
    """
    Scores a single job description using Gemini API with structured JSON output.
    Falls back to deterministic scoring if API key is not configured.
    """
    if not description:
        logger.warning(f"No description available for job {job_id}. Skipping scoring.")
        return None

    # Check if API Key is configured
    if not GEMINI_API_KEY:
        mock_result = generate_mock_score(title, description)
        update_job_score(
            job_id=job_id,
            match_score=mock_result["match_score"],
            key_technologies=mock_result["key_technologies"],
            fit_reasons=mock_result["fit_reasons"],
            action_item=mock_result["action_item"],
            status="scored"
        )
        return mock_result

    logger.info(f"Invoking Gemini API to score job {job_id}: {title} at {company}")
    
    prompt = f"""
You are an expert Senior Data Engineer and recruiter assistant. Your job is to analyze the following job description and score it against the candidate's profile.

---
### CANDIDATE PROFILE:
{CANDIDATE_PROFILE}

### CRITICAL FILTERING RULE:
{CRITICAL_FILTERING_RULE}
---

### JOB TO EVALUATE:
Title: {title}
Company: {company}
Description:
{description}

---
Evaluate the job and output a structured JSON response matching the following schema:
{{
  "match_score": <int: 1 to 10>,
  "key_technologies": [<string: technologies listed or required>],
  "fit_reasons": "<string: 2-3 sentences explaining your scoring and evaluation>",
  "action_item": "<string: 1-sentence actionable instruction for the candidate>"
}}
"""

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JobScoringModel,
                temperature=0.1
            )
        )
        
        result = json.loads(response.text)
        
        # Save to database
        update_job_score(
            job_id=job_id,
            match_score=result["match_score"],
            key_technologies=result["key_technologies"],
            fit_reasons=result["fit_reasons"],
            action_item=result["action_item"],
            status="scored"
        )
        return result
        
    except Exception as e:
        logger.error(f"Error during Gemini scoring for job {job_id}: {e}")
        # Secondary fallback if SDK library fails
        try:
            logger.info("Attempting standard REST fallback for Gemini...")
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(text_content)
                update_job_score(
                    job_id=job_id,
                    match_score=result["match_score"],
                    key_technologies=result.get("key_technologies", []),
                    fit_reasons=result.get("fit_reasons", ""),
                    action_item=result.get("action_item", ""),
                    status="scored"
                )
                return result
        except Exception as fallback_err:
            logger.error(f"Gemini REST Fallback also failed: {fallback_err}")
            
        return None

def run_scoring_pipeline() -> int:
    """Scores all unscored jobs in the database."""
    from src.database import get_unscored_jobs
    
    unscored_jobs = get_unscored_jobs()
    scored_count = 0
    
    logger.info(f"Found {len(unscored_jobs)} jobs awaiting scoring.")
    for job in unscored_jobs:
        score_res = score_job(
            job_id=job["job_id"],
            title=job["title"],
            company=job["company"],
            description=job["description"]
        )
        if score_res:
            scored_count += 1
            
    return scored_count
