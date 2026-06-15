import os
import json
import argparse
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY, GEMINI_MODEL

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cv_tailor")

class TailoredOutput(BaseModel):
    company_name: str = Field(..., description="The name of the company hiring for this role.")
    extracted_keywords: list[str] = Field(..., description="Key technical and business terms extracted from the job description.")
    top_tech_stack: list[str] = Field(..., description="The top 3 technologies in the job description that align with the candidate's profile.")
    business_pain_points: str = Field(..., description="Core business challenges the hiring team is facing (e.g., query latency, workflow automation, analytical reporting scaling).")
    tailored_summary: str = Field(..., description="ATS-optimized professional summary block for David Ben Ami, emphasizing relevant stack, modern data stack, and experience without fabricating skills.")
    tailored_bullet_points: list[str] = Field(..., description="List of 5-6 customized experience bullet points representing David's professional work, adjusted to emphasize technologies and tasks required by the JD.")
    outreach_message: str = Field(..., description="A 3-4 sentence targeted LinkedIn message directed to a Recruiter or Hiring Manager at the company, framing David as the perfect solution to their tech needs.")

def create_mock_tailoring(company_name: str, jd_text: str, master_cv_content: str) -> dict:
    """Deterministic fallback for tailoring when GEMINI_API_KEY is not configured."""
    logger.info("Using rules-based mock tailoring fallback.")
    
    # Simple keyword extraction
    jd_lower = jd_text.lower()
    keywords = []
    for kw in ["dbt", "airflow", "bigquery", "pyspark", "pandas", "docker", "sql", "data modeling", "analytics engineering"]:
        if kw in jd_lower:
            keywords.append(kw)
            
    top_tech = [k.capitalize() if k != "dbt" else "dbt" for k in keywords[:3]]
    if not top_tech:
        top_tech = ["Python", "SQL", "dbt"]
        
    pain_points = "Scaling data delivery to analytical dashboards and resolving data pipeline latency."
    if "airflow" in jd_lower:
        pain_points = "Orchestrating complex dependencies, resolving scheduling bottlenecks, and ensuring data consistency."
    elif "dbt" in jd_lower:
        pain_points = "Establishing sound data modeling, modular transformations, and optimizing analytical warehouse costs."

    tailored_summary = (
        f"Data Engineer & BI Developer with 3 to 4 years of experience specializing in building robust data "
        f"architectures and analytics engineering. Proficient in {', '.join(top_tech)} to design and optimize "
        f"scalable automated pipelines. Heavy preference and deep expertise in Modern Data Stack (MDS) principles, "
        f"structured data modeling, and containerized deployments."
    )

    tailored_bullets = [
        f"Architected, built, and maintained scalable data pipelines using Python and SQL to process operational records, leveraging {', '.join(top_tech)} for pipeline reliability.",
        "Implemented and optimized data models in Google BigQuery using dbt, reducing query execution times by 30% and cloud spend by 15%.",
        "Orchestrated complex workflow dependencies with Apache Airflow, ensuring high availability and robust error alerting.",
        "Containerized data applications using Docker for seamless local development and production deployments.",
        "Collaborated closely with Product and Analytics teams to define KPIs and construct actionable dashboards."
    ]

    outreach = (
        f"Hi there! I noticed you are hiring a Data Engineer at {company_name} to work on your data pipeline infrastructure. "
        f"With 3-4 years of experience specializing in {', '.join(top_tech)} and analytics engineering, I've previously reduced warehouse query execution times by 30% using dbt. "
        f"I'd love to chat briefly and see if my background in building automated pipelines fits your team's needs. Thanks!"
    )

    return {
        "company_name": company_name,
        "extracted_keywords": keywords,
        "top_tech_stack": top_tech,
        "business_pain_points": pain_points,
        "tailored_summary": tailored_summary,
        "tailored_bullet_points": tailored_bullets,
        "outreach_message": outreach
    }

def get_tailored_cv_markdown(master_cv: str, summary: str, bullets: list[str]) -> str:
    """Assembles a full tailored markdown CV using the new summary and experience bullets."""
    lines = master_cv.split("\n")
    new_lines = []
    skip = False
    
    # State tracking to replace sections cleanly
    for line in lines:
        if line.startswith("## Profile Summary"):
            new_lines.append(line)
            new_lines.append(summary)
            skip = True
            continue
        elif line.startswith("## Technical Skills"):
            skip = False
            
        if line.startswith("### **Data Engineer & BI Developer** |"):
            new_lines.append(line)
            new_lines.append(lines[lines.index(line) + 1]) # Keep the date line
            for b in bullets:
                new_lines.append(f"* {b}")
            skip = True
            continue
        elif line.startswith("### **BI Developer & Data Analyst** |"):
            skip = False
            
        if skip:
            # Skip old summary or old main bullet points
            if line.strip() == "" and not new_lines[-1].strip() == "":
                new_lines.append("")
            continue
            
        new_lines.append(line)
        
    return "\n".join(new_lines)

def run_tailoring(company_name: str, jd_path: str, output_dir_cv: str, output_dir_outreach: str):
    # 1. Create Directories if they don't exist
    Path(output_dir_cv).mkdir(parents=True, exist_ok=True)
    Path(output_dir_outreach).mkdir(parents=True, exist_ok=True)
    
    # 2. Read Master CV
    master_cv_path = Path(__file__).resolve().parent / "master_cv.md"
    if not master_cv_path.exists():
        logger.error(f"Master CV not found at {master_cv_path}. Exiting.")
        return
        
    with open(master_cv_path, "r", encoding="utf-8") as f:
        master_cv_content = f.read()
        
    # 3. Read Job Description
    jd_file_path = Path(jd_path)
    if not jd_file_path.exists():
        logger.error(f"Job Description file not found at {jd_path}. Exiting.")
        return
        
    with open(jd_file_path, "r", encoding="utf-8") as f:
        jd_content = f.read().strip()
        
    # 4. Tailoring Layer (Gemini or Fallback)
    result = None
    if not GEMINI_API_KEY:
        result = create_mock_tailoring(company_name, jd_content, master_cv_content)
    else:
        logger.info(f"Invoking Gemini API ({GEMINI_MODEL}) to tailor CV and construct outreach...")
        
        prompt = f"""
You are an expert Technical Recruiter and Career Coach in the Israeli High-Tech sector.
Analyze the following Job Description (JD) and tailor David Ben Ami's CV Profile Summary and main experience bullet points to match it. Also, draft a highly targeted, 3-4 sentence LinkedIn outreach message directed to the Hiring Manager or Recruiter.

---
### CANDIDATE MASTER CV:
{master_cv_content}

---
### TARGET JOB DESCRIPTION:
Company: {company_name}
JD Text:
{jd_content}

---
### RULES:
1. ATS Optimization: Extract critical keywords and required technologies, and highlight David's matching skills (Python, SQL, dbt, Airflow, Docker, PySpark, BigQuery).
2. STICK TO REAL EXPERIENCE: Do NOT fabricate or invent any skills, technologies, years of experience, or responsibilities. Only adjust the style, focus, terminology, and keyword structure of David's existing accomplishments.
3. LinkedIn Outreach: Must be exactly 3 to 4 sentences. Frame David as a direct solution to the team's engineering/business pain points mentioned in the JD.
4. Output JSON format matching the schema.
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
                    response_schema=TailoredOutput,
                    temperature=0.2
                )
            )
            result = json.loads(response.text)
        except Exception as e:
            logger.error(f"Error calling Gemini SDK: {e}. Falling back to REST method...")
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.2
                    }
                }
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    text_content = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    result = json.loads(text_content)
            except Exception as fallback_err:
                logger.error(f"REST Fallback also failed: {fallback_err}")
                
        if not result:
            logger.warning("Tailoring failed, using mock tailoring as a safety fallback.")
            result = create_mock_tailoring(company_name, jd_content, master_cv_content)

    # 5. Output Construction & Saving
    clean_company_name = "".join([c if c.isalnum() else "_" for c in company_name.lower().replace(" ", "_")])
    
    # Save Tailored CV
    cv_output_path = Path(output_dir_cv) / f"cv_{clean_company_name}.md"
    tailored_cv_md = get_tailored_cv_markdown(
        master_cv=master_cv_content,
        summary=result["tailored_summary"],
        bullets=result["tailored_bullet_points"]
    )
    with open(cv_output_path, "w", encoding="utf-8") as f:
        f.write(tailored_cv_md)
    logger.info(f"Tailored CV successfully written to: {cv_output_path}")

    # Save Outreach Message
    outreach_output_path = Path(output_dir_outreach) / f"message_{clean_company_name}.txt"
    with open(outreach_output_path, "w", encoding="utf-8") as f:
        f.write(result["outreach_message"])
    logger.info(f"LinkedIn Outreach successfully written to: {outreach_output_path}")

    # Print summary information
    print("\n" + "="*70)
    print(f"🎯  CV TAILORING RESULTS FOR: {company_name.upper()}")
    print("="*70)
    print(f"🔍  Keywords Extracted: {', '.join(result.get('extracted_keywords', []))}")
    print(f"🛠  Aligned Stack: {', '.join(result.get('top_tech_stack', []))}")
    print(f"🔥  Pain Points Identified: {result.get('business_pain_points', '')}")
    print("-"*70)
    print("💬  LINKEDIN OUTREACH MESSAGE (3-4 Sentences):")
    print(result.get("outreach_message", ""))
    print("="*70 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CV Tailoring & LinkedIn Outreach Agent")
    parser.add_argument("--company", required=True, help="Name of the company you are targeting.")
    parser.add_argument("--jd-file", required=True, help="Path to the local text file containing the job description.")
    parser.add_argument("--cv-dir", default="tailored_cvs", help="Output folder for the tailored CVs.")
    parser.add_argument("--message-dir", default="outreach_messages", help="Output folder for outreach messages.")
    
    args = parser.parse_args()
    run_tailoring(
        company_name=args.company,
        jd_path=args.jd_file,
        output_dir_cv=args.cv_dir,
        output_dir_outreach=args.message_dir
    )
