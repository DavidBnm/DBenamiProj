import requests
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, MIN_SCORE_THRESHOLD
from src.database import get_db_connection

logger = logging.getLogger(__name__)

def send_telegram_message(message: str) -> bool:
    """Sends a message to the configured Telegram chat/channel using HTML format."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot Token or Chat ID not configured. Skipping Telegram notification.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram notification sent successfully.")
            return True
        else:
            logger.error(f"Failed to send Telegram message: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False

def format_job_message(job: dict) -> str:
    """Formats the job details into an HTML message for Telegram."""
    score = job.get("match_score", 0)
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    link = job.get("link", "#")
    fit_reasons = job.get("fit_reasons", "No reasons provided.")
    action_item = job.get("action_item", "No action items.")
    techs = job.get("key_technologies", [])
    
    tech_str = ", ".join(techs) if isinstance(techs, list) else str(techs)
    
    emoji = "🔥" if score >= 9 else "🚀"
    
    message = (
        f"{emoji} <b>New Job Match: {score}/10</b>\n"
        f"<b>Title:</b> {title}\n"
        f"<b>Company:</b> {company}\n\n"
        f"🎯 <b>Fit Analysis:</b>\n"
        f"<i>{fit_reasons}</i>\n\n"
        f"🛠 <b>Stack:</b> {tech_str}\n"
        f"👉 <b>Action:</b> {action_item}\n\n"
        f"🔗 <a href='{link}'>View Job Posting</a>"
    )
    return message

def print_console_notification(job: dict):
    """Fallback printed to standard output when Telegram isn't configured."""
    score = job.get("match_score", 0)
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    link = job.get("link", "#")
    fit_reasons = job.get("fit_reasons", "No reasons provided.")
    action_item = job.get("action_item", "No action items.")
    techs = job.get("key_technologies", [])
    
    print("\n" + "="*60)
    print(f"📢  NOTIFICATION ALERT: MATCH SCORE {score}/10")
    print(f"💼  {title} at {company}")
    print(f"🔗  {link}")
    print("-"*60)
    print(f"🎯  Fit: {fit_reasons}")
    print(f"🛠  Stack: {', '.join(techs) if isinstance(techs, list) else techs}")
    print(f"👉  Action: {action_item}")
    print("="*60 + "\n")

def run_delivery_pipeline() -> int:
    """
    Finds all scored jobs that have not been notified/skipped.
    Alerts only when the score meets the minimum threshold (default: >= 8).
    Marks jobs as 'notified' or 'skipped' in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Select all jobs that are 'scored'
    cursor.execute("SELECT * FROM jobs WHERE status = 'scored'")
    rows = cursor.fetchall()
    conn.close()
    
    notified_count = 0
    
    import json
    for row in rows:
        job = dict(row)
        if job["key_technologies"]:
            try:
                job["key_technologies"] = json.loads(job["key_technologies"])
            except Exception:
                pass
                
        job_id = job["job_id"]
        score = job["match_score"]
        
        # Decide if we notify or skip based on threshold
        if score >= MIN_SCORE_THRESHOLD:
            # Send Notification
            message = format_job_message(job)
            telegram_sent = send_telegram_message(message)
            print_console_notification(job)
            
            # Update status in db
            new_status = "notified" if telegram_sent else "notified_console"
            notified_count += 1
        else:
            new_status = "skipped"
            logger.info(f"Job {job_id} scored {score} (< {MIN_SCORE_THRESHOLD}), skipping notification.")
            
        # Update database status
        conn_update = get_db_connection()
        cursor_update = conn_update.cursor()
        cursor_update.execute("UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?", (new_status, job_id))
        conn_update.commit()
        conn_update.close()
        
    return notified_count
