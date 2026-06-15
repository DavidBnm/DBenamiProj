import os
import sqlite3
import pytest
from src.ingestion import extract_job_id
from src.database import init_db, save_raw_job, get_unscored_jobs, is_job_processed, update_job_score, get_job
from src.scoring import generate_mock_score

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    """Sets up a temporary SQLite database for testing, isolated from the production one."""
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setenv("DATABASE_PATH", str(test_db))
    monkeypatch.setattr("src.database.DATABASE_PATH", str(test_db))
    monkeypatch.setattr("config.DATABASE_PATH", str(test_db))
    init_db()
    yield test_db
    # Cleanup database file if exists
    if test_db.exists():
        os.remove(test_db)

def test_extract_job_id():
    """Test that LinkedIn Job IDs are correctly extracted from URLs."""
    url1 = "https://www.linkedin.com/jobs/view/data-engineer-at-company-3847293847/?activeDesign=true"
    url2 = "https://il.linkedin.com/jobs/view/3847293847"
    url3 = "https://www.linkedin.com/jobs/view/analytics-engineer-3847293847"
    url4 = "https://www.linkedin.com/jobs/search/?currentJobId=3847293847&keywords=Data%20Engineer"
    
    assert extract_job_id(url1) == "3847293847"
    assert extract_job_id(url2) == "3847293847"
    assert extract_job_id(url3) == "3847293847"
    assert extract_job_id(url4) == "3847293847"
    assert extract_job_id("https://google.com") is None

def test_database_operations():
    """Test standard database insert, update, state checks, and retrievals."""
    job_id = "test-job-999"
    title = "Test Data Engineer"
    company = "Data Corp"
    link = "https://example.com/test-job-999"
    desc = "Need a Mid Data Engineer with 3 years experience. Must know python and SQL."
    
    # Check job is not processed initially
    assert not is_job_processed(job_id)
    
    # Save raw job
    saved = save_raw_job(job_id, title, company, link, desc)
    assert saved
    assert is_job_processed(job_id)
    
    # Get unscored jobs
    unscored = get_unscored_jobs()
    assert len(unscored) == 1
    assert unscored[0]["job_id"] == job_id
    assert unscored[0]["status"] == "scraped"
    
    # Update score
    updated = update_job_score(
        job_id=job_id,
        match_score=9,
        key_technologies=["Python", "SQL"],
        fit_reasons="Great match",
        action_item="Apply now",
        status="scored"
    )
    assert updated
    
    # Check job updated
    job = get_job(job_id)
    assert job["match_score"] == 9
    assert job["status"] == "scored"
    assert "Python" in job["key_technologies"]
    
    # Ensure it's no longer in unscored jobs
    assert len(get_unscored_jobs()) == 0

def test_mock_scoring_rules():
    """Test our scoring logic against the candidate profile and seniority limits."""
    # 1. Matching Job (3 years experience, MDS stack)
    matching_desc = (
        "We are looking for a Data Engineer. Requirements: 3-4 years experience. "
        "Proficient with Python, SQL, dbt, and Airflow. Experience with Docker is nice."
    )
    res_match = generate_mock_score("Data Engineer", matching_desc)
    assert res_match["match_score"] >= 8
    assert "dbt" in res_match["key_technologies"]
    assert "Airflow" in res_match["key_technologies"]
    
    # 2. Senior / High Experience Job (Should filter out or score low)
    senior_desc = (
        "We are seeking a Senior Principal Data Engineer to lead our architecture. "
        "Must have 8+ years of experience. Experience with AWS, Scala, Spark, and team management is a must."
    )
    res_senior = generate_mock_score("Senior Principal Data Engineer", senior_desc)
    assert res_senior["match_score"] <= 4  # Should penalize heavily
    assert "Skip this position" in res_senior["action_item"]
