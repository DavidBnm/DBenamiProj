import sqlite3
import json
import logging
from datetime import datetime
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            link TEXT NOT NULL,
            description TEXT,
            match_score INTEGER,
            key_technologies TEXT, -- JSON array stored as text
            fit_reasons TEXT,
            action_item TEXT,
            status TEXT DEFAULT 'scraped', -- 'scraped', 'scored', 'notified', 'skipped', 'error'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

def is_job_processed(job_id: str) -> bool:
    """Checks if a job has already been scraped and saved."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_raw_job(job_id: str, title: str, company: str, link: str, description: str = None) -> bool:
    """Saves a new raw job entry to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO jobs (job_id, title, company, link, description, status)
            VALUES (?, ?, ?, ?, ?, 'scraped')
            ON CONFLICT(job_id) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                link = excluded.link,
                description = COALESCE(excluded.description, jobs.description),
                updated_at = CURRENT_TIMESTAMP
        """, (job_id, title, company, link, description))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving job {job_id}: {e}")
        return False
    finally:
        conn.close()

def update_job_score(job_id: str, match_score: int, key_technologies: list, fit_reasons: str, action_item: str, status: str) -> bool:
    """Updates job scoring and status post LLM analysis."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        tech_json = json.dumps(key_technologies)
        cursor.execute("""
            UPDATE jobs
            SET match_score = ?,
                key_technologies = ?,
                fit_reasons = ?,
                action_item = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
        """, (match_score, tech_json, fit_reasons, action_item, status, job_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating job score for {job_id}: {e}")
        return False
    finally:
        conn.close()

def get_unscored_jobs() -> list:
    """Retrieves all jobs that have been scraped but not yet scored."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE status = 'scraped'")
    rows = cursor.fetchall()
    jobs = []
    for row in rows:
        job = dict(row)
        if job['key_technologies']:
            job['key_technologies'] = json.loads(job['key_technologies'])
        jobs.append(job)
    conn.close()
    return jobs

def get_job(job_id: str) -> dict:
    """Gets a specific job details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        job = dict(row)
        if job['key_technologies']:
            job['key_technologies'] = json.loads(job['key_technologies'])
        return job
    return None
