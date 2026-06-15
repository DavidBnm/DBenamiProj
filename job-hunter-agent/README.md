# Agentic Job Hunter for Israel Data Engineering Roles

An automated, containerized Agentic Job Hunter system built to scan, filter, score, and notify you of Mid-Level / Mid-Senior Data Engineering, BI Developer, and Analytics Engineer roles in Israel.

## System Architecture

The pipeline consists of four modular layers:
1. **Ingestion Layer (`src/ingestion.py`)**: Connects to the public LinkedIn guest job board (without requiring logins or API keys) to find listings for "Data Engineer", "BI Developer", and "Analytics Engineer" in Israel. Rotates user agents and includes random delay intervals to avoid rate limits. It has a fallback mock-jobs loader for offline development and testing.
2. **AI Scoring & Filtering Layer (`src/scoring.py`)**: Leverages the Gemini API (`gemini-2.5-flash`) to evaluate each job posting against your specific profile, strictly filtering out roles demanding 7+ years of experience or management responsibilities. Supports a deterministic keyword scoring fallback if no `GEMINI_API_KEY` is provided.
3. **State Management (`src/database.py`)**: Uses an SQLite database (`jobs.db`) to ensure jobs are deduplicated and that duplicate notifications are never sent.
4. **Delivery Layer (`src/delivery.py`)**: Sends rich, HTML-formatted notifications to a Telegram chat/channel for roles that score `8/10` or above. Falls back to a clear terminal alert template if Telegram credentials are not configured.

---

## Getting Started

### 1. Prerequisites
- Python 3.11+ or Docker
- A Telegram bot token and chat ID (optional, but recommended for live alerts)
- A Gemini API key (optional, but recommended for AI-powered scoring)

### 2. Configuration Setup
Copy the configuration template and populate it with your keys:
```bash
cp .env.example .env
```

Open `.env` and configure:
```ini
# Gemini LLM Configuration
GEMINI_API_KEY=your_actual_gemini_api_key

# Telegram Notification Configuration (Optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Pipeline Settings
SCRAPE_PAGES_LIMIT=3
MIN_SCORE_THRESHOLD=8
DATABASE_PATH=jobs.db
```

---

## Local Execution

We recommend creating a Python virtual environment to manage dependencies:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run Tests
To verify all pipeline logic (ingestion regex, database operations, and scoring criteria):
```bash
pytest tests/
```

### Run the Pipeline
Run the main orchestrator:
```bash
python main.py
```
*Note: If no live jobs are fetched (due to network restriction or rate limits), the pipeline automatically loads rich mock job descriptions containing matching and non-matching profiles to demonstrate the system scoring and sending alerts.*

---

## Docker Execution

To build and run the pipeline seamlessly inside a Docker container:

### 1. Build the Docker Image
```bash
docker build -t job-hunter .
```

### 2. Run the Container
Pass your environment variables file to the container:
```bash
docker run --env-file .env -v $(pwd)/jobs.db:/app/jobs.db job-hunter
```
*(The `-v` flag mounts the local `jobs.db` database file so the pipeline state is preserved across container runs).*
