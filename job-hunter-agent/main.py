import logging
import argparse
from src.database import init_db
from src.ingestion import ingest_jobs
from src.scoring import run_scoring_pipeline
from src.delivery import run_delivery_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("job_hunter")

def run_pipeline(use_fallback: bool = True):
    """Orchestrates the whole agentic job hunt process."""
    logger.info("Starting Agentic Job Hunter pipeline...")
    
    # Step 1: Initialize Database
    logger.info("Initializing local database...")
    init_db()
    
    # Step 2: Run Ingestion
    logger.info("Running Ingestion Layer (fetching job postings)...")
    new_scraped = ingest_jobs(use_fallback=use_fallback)
    logger.info(f"Ingestion completed. {new_scraped} new jobs added/updated in the database.")
    
    # Step 3: Run AI Scoring
    logger.info("Running AI Scoring & Filtering Layer...")
    scored = run_scoring_pipeline()
    logger.info(f"Scoring completed. Evaluated {scored} new jobs.")
    
    # Step 4: Run Notification Delivery
    logger.info("Running Notification Delivery Layer...")
    notified = run_delivery_pipeline()
    logger.info(f"Delivery completed. Dispatched {notified} high-match notifications.")
    
    logger.info("Pipeline run finished successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic Job Hunter for Data Engineers in Israel")
    parser.add_argument(
        "--no-fallback",
        action="store_false",
        dest="use_fallback",
        help="Disable mock job loading when scraper finds 0 items (useful for strict production runs)."
    )
    args = parser.parse_args()
    
    run_pipeline(use_fallback=args.use_fallback)
