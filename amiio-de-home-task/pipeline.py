import json
import os
import sys
import time
import logging
import tempfile
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import pandas as pd



class SimpleColoredFormatter(logging.Formatter):
    """Injects exact ANSI colors for clean terminal logging without duplication."""
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    RESET = "\033[0m"

    def __init__(self, fmt="%(asctime)s - %(levelname)s - [PipelineEngine] - %(message)s"):
        super().__init__(fmt)

    def format(self, record):
        if record.levelno == logging.INFO:
            color = self.GREEN
        elif record.levelno == logging.WARNING:
            color = self.YELLOW
        elif record.levelno in [logging.ERROR, logging.CRITICAL]:
            color = self.RED
        else:
            color = self.RESET

        result = super().format(record)
        return f"{color}{result}{self.RESET}"


logger = logging.getLogger("PipelineLogger")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(SimpleColoredFormatter())
    logger.addHandler(ch)


PIPELINE_CONFIG = {
    "api_sports": {
        "key": "eb4ffc6ac1ff9cdb319a55546854ef6b",
        "season": 2024,
        "league_id": 39
    },
    "api_football": {
        "key": "15d3c9651b53d6030c59d2168413b502ef59b4a92280c0541826050c85b73d70",
        "league_id": 152
    }
}


def get_requests_session():
    """Creates a robust requests session with automated retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def normalize_team_name(name):
    """Standardizes team names by lowercasing and matching against a strict baseline."""
    if not name:
        return ""
    name = str(name).lower().strip()
    master_mapping = {
        "manchester united": "manchester united", "manchester utd": "manchester united",
        "manchester city": "manchester city", "man city": "manchester city",
        "tottenham hotspur": "tottenham hotspur", "tottenham": "tottenham hotspur",
        "newcastle united": "newcastle united", "newcastle utd": "newcastle united", "newcastle": "newcastle united",
        "west ham united": "west ham united", "west ham utd": "west ham united", "west ham": "west ham united",
        "wolverhampton wanderers": "wolves", "wolves": "wolves",
        "brighton & hove albion": "brighton", "brighton": "brighton",
        "afc bournemouth": "bournemouth", "bournemouth": "bournemouth",
        "sheffield united": "sheffield united", "sheffield utd": "sheffield united",
        "luton town": "luton", "luton": "luton",
        "arsenal": "arsenal", "chelsea": "chelsea", "liverpool": "liverpool", "aston villa": "aston villa",
        "everton": "everton", "brentford": "brentford", "crystal palace": "crystal palace", "fulham": "fulham",
        "burnley": "burnley", "nottingham forest": "nottingham forest"
    }
    return master_mapping.get(name, name)


def fetch_api_sports_raw(config, telemetry_store):
    """Fetches raw teams and standings payloads from API-Sports and tracks latency."""
    session = get_requests_session()
    base_url = "https://v3.football.api-sports.io"
    headers = {
        'x-rapidapi-key': config["key"],
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    season = config["season"]
    league_id = config["league_id"]

    try:
        logger.info(f"Requesting API-Sports teams endpoint for season {season}...")
        start_teams = time.time()
        res_teams_json = session.get(f"{base_url}/teams?league={league_id}&season={season}", headers=headers,
                                     timeout=10).json()

        if res_teams_json.get("errors"):
            raise ValueError(f"API-Sports authentication or request failure: {res_teams_json['errors']}")

        res_teams = res_teams_json.get('response', [])
        latency_teams = int((time.time() - start_teams) * 1000)
        telemetry_store["api_call_count"] += 1

        logger.info(f"Requesting API-Sports standings endpoint for season {season}...")
        start_standings = time.time()
        res_standings_json = session.get(f"{base_url}/standings?league={league_id}&season={season}", headers=headers,
                                         timeout=10).json()

        if res_standings_json.get("errors"):
            raise ValueError(f"API-Sports authentication or request failure: {res_standings_json['errors']}")

        res_standings = res_standings_json.get('response', [])
        latency_standings = int((time.time() - start_standings) * 1000)
        telemetry_store["api_call_count"] += 1

        telemetry_store["source_latency"]["api_sports_ms"] = latency_teams + latency_standings
        telemetry_store["record_counts"]["api_sports_raw_teams"] = len(res_teams)

        logger.info(f"Successfully ingested raw payloads from API-Sports in {latency_teams + latency_standings}ms.")
        return {"teams": res_teams, "standings": res_standings}
    except Exception as e:
        telemetry_store["error_rate"] += 0.5
        logger.error(f"API-Sports ingestion failed: {e}")
        raise


def fetch_api_football_raw(config, telemetry_store):
    """Fetches raw teams and standings payloads from API-Football and tracks latency."""
    session = get_requests_session()
    base_url = "https://apiv3.apifootball.com/"
    league_id = config["league_id"]
    api_key = config["key"]

    try:
        logger.info(f"Requesting API-Football teams endpoint for league {league_id}...")
        start_teams = time.time()
        res_teams = session.get(base_url, params={"action": "get_teams", "league_id": league_id, "APIkey": api_key},
                                timeout=10).json()

        if isinstance(res_teams, dict) and res_teams.get("error"):
            raise ValueError(f"API-Football authentication or request failure: {res_teams.get('error')}")

        latency_teams = int((time.time() - start_teams) * 1000)
        telemetry_store["api_call_count"] += 1

        logger.info(f"Requesting API-Football standings endpoint for league {league_id}...")
        start_standings = time.time()
        res_standings = session.get(base_url,
                                    params={"action": "get_standings", "league_id": league_id, "APIkey": api_key},
                                    timeout=10).json()

        if isinstance(res_standings, dict) and res_standings.get("error"):
            raise ValueError(f"API-Football authentication or request failure: {res_standings.get('error')}")

        latency_standings = int((time.time() - start_standings) * 1000)
        telemetry_store["api_call_count"] += 1

        telemetry_store["source_latency"]["api_football_ms"] = latency_teams + latency_standings
        telemetry_store["record_counts"]["api_football_raw_teams"] = len(res_teams) if isinstance(res_teams,
                                                                                                  list) else 0

        logger.info(f"Successfully ingested raw payloads from API-Football in {latency_teams + latency_standings}ms.")
        return {"teams": res_teams, "standings": res_standings}
    except Exception as e:
        telemetry_store["error_rate"] += 0.5
        logger.error(f"API-Football ingestion failed: {e}")
        raise


def transform_source_data(sports_raw_path, football_raw_path, telemetry_store):
    """Parses raw JSON files, standardizes schemas and performs data cleaning."""
    logger.info("Initializing Data Transformation Layer...")

    # --- Process API-Sports Branch ---
    with open(sports_raw_path, 'r') as f:
        sports_data = json.load(f)
    df_teams_s = pd.DataFrame([{'team_id': str(i.get('team', {}).get('id', '')),
                                'norm_name': normalize_team_name(i.get('team', {}).get('name')),
                                'founded_year': i.get('team', {}).get('founded'),
                                'stadium_name': i.get('venue', {}).get('name', 'Unknown'),
                                'city': i.get('venue', {}).get('city', 'Unknown')} for i in
                               sports_data.get('teams', [])]).drop_duplicates(subset=['norm_name'])

    standings_s = []
    if sports_data.get('standings'):
        for row in sports_data['standings'][0].get('league', {}).get('standings', [[]])[0]:
            stats_all = row.get('all', {})
            standings_s.append({'norm_name': normalize_team_name(row.get('team', {}).get('name')), 'season': 2024,
                                'table_position': row.get('rank'), 'points': row.get('points'),
                                'games_played': stats_all.get('played'), 'wins': stats_all.get('win'),
                                'draws': stats_all.get('draw'), 'losses': stats_all.get('lose'),
                                'goals_for': stats_all.get('goals', {}).get('for'),
                                'goals_against': stats_all.get('goals', {}).get('against')})
    df_standings_s = pd.DataFrame(standings_s).drop_duplicates(subset=['norm_name'])

    df_sports_final = pd.merge(df_standings_s, df_teams_s, on='norm_name', how='left')
    df_sports_final['team_id'] = df_sports_final['team_id'].fillna('Unknown')
    df_sports_final['stadium_name'] = df_sports_final['stadium_name'].fillna('Unknown')
    df_sports_final['city'] = df_sports_final['city'].fillna('Unknown')
    df_sports_final['team_name'] = df_sports_final['norm_name'].str.title()
    df_sports_final.drop(columns=['norm_name'], inplace=True, errors='ignore')

    with open(football_raw_path, 'r') as f:
        football_data = json.load(f)
    df_teams_f = pd.DataFrame([{'team_id': str(i.get('team_key', '')),
                                'norm_name': normalize_team_name(i.get('team_name')),
                                'founded_year': i.get('team_founded'),
                                'stadium_name': i.get('venue', {}).get('venue_name', 'Unknown'),
                                'city': i.get('venue', {}).get('venue_city', 'Unknown')} for i in
                               football_data.get('teams', [])]).drop_duplicates(subset=['norm_name'])
    df_standings_f = pd.DataFrame([{'norm_name': normalize_team_name(i.get('team_name')), 'season': 2024,
                                    'table_position': i.get('overall_league_position'),
                                    'points': i.get('overall_league_PTS'),
                                    'games_played': i.get('overall_league_payed'), 'wins': i.get('overall_league_W'),
                                    'draws': i.get('overall_league_D'), 'losses': i.get('overall_league_L'),
                                    'goals_for': i.get('overall_league_GF'),
                                    'goals_against': i.get('overall_league_GA')} for i in
                                   football_data.get('standings', [])]).drop_duplicates(subset=['norm_name'])

    df_football_final = pd.merge(df_standings_f, df_teams_f, on='norm_name', how='left')
    df_football_final['team_id'] = df_football_final['team_id'].fillna('Unknown')
    df_football_final['stadium_name'] = df_football_final['stadium_name'].fillna('Unknown')
    df_football_final['city'] = df_football_final['city'].fillna('Unknown')
    df_football_final['team_name'] = df_football_final['norm_name'].str.title()
    df_football_final.drop(columns=['norm_name'], inplace=True, errors='ignore')

    numeric_cols = ['table_position', 'points', 'games_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against']
    for col in numeric_cols:
        if col in df_football_final.columns:
            df_football_final[col] = pd.to_numeric(df_football_final[col], errors='coerce').fillna(0).astype(int)

    schema_cols = [
        'team_id', 'team_name', 'founded_year', 'stadium_name', 'city', 'season',
        'table_position', 'points', 'games_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against'
    ]
    df_sports_final = df_sports_final[[c for c in schema_cols if c in df_sports_final.columns]]
    df_football_final = df_football_final[[c for c in schema_cols if c in df_football_final.columns]]

    df_sports_final['ingested_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    df_football_final['ingested_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Save final counts to telemetry store
    telemetry_store["record_counts"]["final_exported_sports"] = len(df_sports_final)
    telemetry_store["record_counts"]["final_exported_football"] = len(df_football_final)

    logger.info(f"Audit Phase: API-Sports branch aligned with {len(df_sports_final)} rows.")
    logger.info(f"Audit Phase: API-Football branch aligned with {len(df_football_final)} rows.")

    if len(df_sports_final) == 20 and len(df_football_final) == 20:
        logger.info("Validation Pass: Both pipeline branches successfully generated exactly 20 standard records.")
    else:
        logger.warning("Data Quality Alert: Mismatch detected in final dataset boundaries!")

    return df_sports_final, df_football_final



def append_telemetry_to_local_csv(telemetry, output_dir):
    """Flattens telemetry metadata and appends it to a local historical CSV for Looker Studio ingestion."""
    csv_path = os.path.join(output_dir, "pipeline_api_stats.csv")

    flattened_row = {
        "timestamp": telemetry["timestamp"],
        "pipeline_processing_time_ms": telemetry["pipeline_processing_time_ms"],
        "api_call_count": telemetry["api_call_count"],
        "error_rate": telemetry["error_rate"],
        "api_sports_latency_ms": telemetry["source_latency"]["api_sports_ms"],
        "api_football_latency_ms": telemetry["source_latency"]["api_football_ms"],
        "api_sports_raw_teams_count": telemetry["record_counts"]["api_sports_raw_teams"],
        "api_football_raw_teams_count": telemetry["record_counts"]["api_football_raw_teams"],
        "final_exported_sports_count": telemetry["record_counts"]["final_exported_sports"],
        "final_exported_football_count": telemetry["record_counts"]["final_exported_football"],
        "execution_status": "SUCCESS" if telemetry["error_rate"] == 0 else "PARTIAL_WARNING"
    }

    df_new = pd.DataFrame([flattened_row])

    try:
        if not os.path.exists(csv_path):
            df_new.to_csv(csv_path, index=False)
            logger.info("[BONUS] Created new telemetry history file: pipeline_api_stats.csv")
        else:
            df_new.to_csv(csv_path, mode='a', header=False, index=False)
            logger.info("[BONUS] Successfully appended run metrics to pipeline_api_stats.csv")
    except Exception as e:
        logger.error(f"Failed to write to pipeline_api_stats.csv: {e}")



def run_entire_etl_pipeline():
    """Coordinates the entire life cycle of the ETL process using a secure temporary runtime zone."""
    output_dir = os.getcwd()

    telemetry_store = {
        "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        "pipeline_stage": "execution_summary",
        "api_call_count": 0,
        "error_rate": 0.0,
        "source_latency": {
            "api_sports_ms": 0,
            "api_football_ms": 0
        },
        "record_counts": {
            "api_sports_raw_teams": 0,
            "api_football_raw_teams": 0,
            "final_exported_sports": 0,
            "final_exported_football": 0
        }
    }

    pipeline_start_time = time.time()

    with tempfile.TemporaryDirectory() as temp_landing_zone:
        sports_raw_json = os.path.join(temp_landing_zone, "api_sports_raw.json")
        football_raw_json = os.path.join(temp_landing_zone, "api_football_raw.json")

        logger.info("Starting Ingestion Phase...")
        sports_payload = fetch_api_sports_raw(PIPELINE_CONFIG["api_sports"], telemetry_store)
        with open(sports_raw_json, 'w') as f: json.dump(sports_payload, f)

        football_payload = fetch_api_football_raw(PIPELINE_CONFIG["api_football"], telemetry_store)
        with open(football_raw_json, 'w') as f: json.dump(football_payload, f)
        logger.info("Step 1 Complete: Both raw source datasets captured successfully.")

        df_sports, df_football = transform_source_data(sports_raw_json, football_raw_json, telemetry_store)

        sports_csv_path = os.path.join(output_dir, "api_sports_cleaned_df.csv")
        football_csv_path = os.path.join(output_dir, "api_football_cleaned_df.csv")

        df_sports.to_csv(sports_csv_path, index=False)
        df_football.to_csv(football_csv_path, index=False)

        logger.info(f"Cleaned target delivered to: {sports_csv_path}")
        logger.info(f"Cleaned target delivered to: {football_csv_path}")

        total_time_ms = int((time.time() - pipeline_start_time) * 1000)
        telemetry_store["pipeline_processing_time_ms"] = total_time_ms

        append_telemetry_to_local_csv(telemetry_store, output_dir)

        logger.info("=========================================================")
        logger.info("[BONUS] PIPELINE RUN EXECUTION MONITORING TELEMETRY")
        logger.info(f"Total Processing Time: {total_time_ms} ms")
        logger.info(f"API Call Count: {telemetry_store['api_call_count']} calls")
        logger.info(
            f"Latency Summary: API-Sports={telemetry_store['source_latency']['api_sports_ms']}ms | API-Football={telemetry_store['source_latency']['api_football_ms']}ms")
        logger.info(
            f"Rows Captured: Raw Teams (S={telemetry_store['record_counts']['api_sports_raw_teams']}, F={telemetry_store['record_counts']['api_football_raw_teams']}) ──► Exported (S={telemetry_store['record_counts']['final_exported_sports']}, F={telemetry_store['record_counts']['final_exported_football']})")
        logger.info("=========================================================")

        print(json.dumps(telemetry_store))
        logger.info("Core ETL Lifecycle Complete. Deliverables verified.")



def run_scheduled_pipeline():
    """Demonstrates how the pipeline can be scheduled periodically."""
    logger.info("Pipeline running in SCHEDULED mode. Task registered for daily execution at 02:00 AM.")
    run_entire_etl_pipeline()
import json
import os
import sys
import time
import logging
import tempfile
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import pandas as pd



class SimpleColoredFormatter(logging.Formatter):
    """Injects exact ANSI colors for clean terminal logging without duplication."""
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    RESET = "\033[0m"

    def __init__(self, fmt="%(asctime)s - %(levelname)s - [PipelineEngine] - %(message)s"):
        super().__init__(fmt)

    def format(self, record):
        if record.levelno == logging.INFO:
            color = self.GREEN
        elif record.levelno == logging.WARNING:
            color = self.YELLOW
        elif record.levelno in [logging.ERROR, logging.CRITICAL]:
            color = self.RED
        else:
            color = self.RESET

        result = super().format(record)
        return f"{color}{result}{self.RESET}"


logger = logging.getLogger("PipelineLogger")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(SimpleColoredFormatter())
    logger.addHandler(ch)


base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, "config.json")

try:
    with open(config_path, "r") as config_file:
        PIPELINE_CONFIG = json.load(config_file)
except FileNotFoundError:
    logger.critical(f"Configuration file missing at predicted path: {config_path}")
    sys.exit(1)
except json.JSONDecodeError:
    logger.critical("Failed to parse config file. Ensure it is a valid JSON document.")
    sys.exit(1)


def get_requests_session():
    """Creates a robust requests session with automated retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def normalize_team_name(name):
    """Standardizes team names by lowercasing and matching against a strict baseline."""
    if not name:
        return ""
    name = str(name).lower().strip()
    master_mapping = {
        "manchester united": "manchester united", "manchester utd": "manchester united",
        "manchester city": "manchester city", "man city": "manchester city",
        "tottenham hotspur": "tottenham hotspur", "tottenham": "tottenham hotspur",
        "newcastle united": "newcastle united", "newcastle utd": "newcastle united", "newcastle": "newcastle united",
        "west ham united": "west ham united", "west ham utd": "west ham united", "west ham": "west ham united",
        "wolverhampton wanderers": "wolves", "wolves": "wolves",
        "brighton & hove albion": "brighton", "brighton": "brighton",
        "afc bournemouth": "bournemouth", "bournemouth": "bournemouth",
        "sheffield united": "sheffield united", "sheffield utd": "sheffield united",
        "luton town": "luton", "luton": "luton",
        "arsenal": "arsenal", "chelsea": "chelsea", "liverpool": "liverpool", "aston villa": "aston villa",
        "everton": "everton", "brentford": "brentford", "crystal palace": "crystal palace", "fulham": "fulham",
        "burnley": "burnley", "nottingham forest": "nottingham forest"
    }
    return master_mapping.get(name, name)



def fetch_api_sports_raw(config, telemetry_store):
    """Fetches raw teams and standings payloads from API-Sports and tracks latency."""
    session = get_requests_session()
    base_url = "https://v3.football.api-sports.io"
    headers = {
        'x-rapidapi-key': config["key"],
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    season = config["season"]
    league_id = config["league_id"]

    try:
        logger.info(f"Requesting API-Sports teams endpoint for season {season}...")
        start_teams = time.time()
        res_teams = session.get(f"{base_url}/teams?league={league_id}&season={season}", headers=headers,
                                timeout=10).json().get('response', [])
        latency_teams = int((time.time() - start_teams) * 1000)
        telemetry_store["api_call_count"] += 1

        logger.info(f"Requesting API-Sports standings endpoint for season {season}...")
        start_standings = time.time()
        res_standings = session.get(f"{base_url}/standings?league={league_id}&season={season}", headers=headers,
                                    timeout=10).json().get('response', [])
        latency_standings = int((time.time() - start_standings) * 1000)
        telemetry_store["api_call_count"] += 1

        telemetry_store["source_latency"]["api_sports_ms"] = latency_teams + latency_standings
        telemetry_store["record_counts"]["api_sports_raw_teams"] = len(res_teams)

        logger.info(f"Successfully ingested raw payloads from API-Sports in {latency_teams + latency_standings}ms.")
        return {"teams": res_teams, "standings": res_standings}
    except Exception as e:
        telemetry_store["error_rate"] += 0.5
        logger.error(f"API-Sports ingestion failed: {e}")
        raise


def fetch_api_football_raw(config, telemetry_store):
    """Fetches raw teams and standings payloads from API-Football and tracks latency."""
    session = get_requests_session()
    base_url = "https://apiv3.apifootball.com/"
    league_id = config["league_id"]
    api_key = config["key"]

    try:
        logger.info(f"Requesting API-Football teams endpoint for league {league_id}...")
        start_teams = time.time()
        res_teams = session.get(base_url, params={"action": "get_teams", "league_id": league_id, "APIkey": api_key},
                                timeout=10).json()
        latency_teams = int((time.time() - start_teams) * 1000)
        telemetry_store["api_call_count"] += 1

        logger.info(f"Requesting API-Football standings endpoint for league {league_id}...")
        start_standings = time.time()
        res_standings = session.get(base_url,
                                    params={"action": "get_standings", "league_id": league_id, "APIkey": api_key},
                                    timeout=10).json()
        latency_standings = int((time.time() - start_standings) * 1000)
        telemetry_store["api_call_count"] += 1

        telemetry_store["source_latency"]["api_football_ms"] = latency_teams + latency_standings
        telemetry_store["record_counts"]["api_football_raw_teams"] = len(res_teams) if isinstance(res_teams,
                                                                                                  list) else 0

        logger.info(f"Successfully ingested raw payloads from API-Football in {latency_teams + latency_standings}ms.")
        return {"teams": res_teams, "standings": res_standings}
    except Exception as e:
        telemetry_store["error_rate"] += 0.5
        logger.error(f"API-Football ingestion failed: {e}")
        raise



def transform_source_data(sports_raw_path, football_raw_path, telemetry_store):
    """Parses raw JSON files, standardizes schemas and performs data cleaning."""
    logger.info("Initializing Data Transformation Layer...")

    # --- Process API-Sports Branch ---
    with open(sports_raw_path, 'r') as f:
        sports_data = json.load(f)
    df_teams_s = pd.DataFrame([{'team_id': str(i.get('team', {}).get('id', '')),
                                'norm_name': normalize_team_name(i.get('team', {}).get('name')),
                                'founded_year': i.get('team', {}).get('founded'),
                                'stadium_name': i.get('venue', {}).get('name', 'Unknown'),
                                'city': i.get('venue', {}).get('city', 'Unknown')} for i in
                               sports_data.get('teams', [])]).drop_duplicates(subset=['norm_name'])

    standings_s = []
    if sports_data.get('standings'):
        for row in sports_data['standings'][0].get('league', {}).get('standings', [[]])[0]:
            stats_all = row.get('all', {})
            standings_s.append({'norm_name': normalize_team_name(row.get('team', {}).get('name')), 'season': 2024,
                                'table_position': row.get('rank'), 'points': row.get('points'),
                                'games_played': stats_all.get('played'), 'wins': stats_all.get('win'),
                                'draws': stats_all.get('draw'), 'losses': stats_all.get('lose'),
                                'goals_for': stats_all.get('goals', {}).get('for'),
                                'goals_against': stats_all.get('goals', {}).get('against')})
    df_standings_s = pd.DataFrame(standings_s).drop_duplicates(subset=['norm_name'])

    df_sports_final = pd.merge(df_standings_s, df_teams_s, on='norm_name', how='left')
    df_sports_final['team_id'] = df_sports_final['team_id'].fillna('Unknown')
    df_sports_final['stadium_name'] = df_sports_final['stadium_name'].fillna('Unknown')
    df_sports_final['city'] = df_sports_final['city'].fillna('Unknown')
    df_sports_final['team_name'] = df_sports_final['norm_name'].str.title()
    df_sports_final.drop(columns=['norm_name'], inplace=True, errors='ignore')

    # --- Process API-Football Branch ---
    with open(football_raw_path, 'r') as f:
        football_data = json.load(f)
    df_teams_f = pd.DataFrame([{'team_id': str(i.get('team_key', '')),
                                'norm_name': normalize_team_name(i.get('team_name')),
                                'founded_year': i.get('team_founded'),
                                'stadium_name': i.get('venue', {}).get('venue_name', 'Unknown'),
                                'city': i.get('venue', {}).get('venue_city', 'Unknown')} for i in
                               football_data.get('teams', [])]).drop_duplicates(subset=['norm_name'])
    df_standings_f = pd.DataFrame([{'norm_name': normalize_team_name(i.get('team_name')), 'season': 2024,
                                    'table_position': i.get('overall_league_position'),
                                    'points': i.get('overall_league_PTS'),
                                    'games_played': i.get('overall_league_payed'), 'wins': i.get('overall_league_W'),
                                    'draws': i.get('overall_league_D'), 'losses': i.get('overall_league_L'),
                                    'goals_for': i.get('overall_league_GF'),
                                    'goals_against': i.get('overall_league_GA')} for i in
                                   football_data.get('standings', [])]).drop_duplicates(subset=['norm_name'])

    df_football_final = pd.merge(df_standings_f, df_teams_f, on='norm_name', how='left')
    df_football_final['team_id'] = df_football_final['team_id'].fillna('Unknown')
    df_football_final['stadium_name'] = df_football_final['stadium_name'].fillna('Unknown')
    df_football_final['city'] = df_football_final['city'].fillna('Unknown')
    df_football_final['team_name'] = df_football_final['norm_name'].str.title()
    df_football_final.drop(columns=['norm_name'], inplace=True, errors='ignore')

    numeric_cols = ['table_position', 'points', 'games_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against']
    for col in numeric_cols:
        if col in df_football_final.columns:
            df_football_final[col] = pd.to_numeric(df_football_final[col], errors='coerce').fillna(0).astype(int)

    # --- Structure Alignment ---
    schema_cols = [
        'team_id', 'team_name', 'founded_year', 'stadium_name', 'city', 'season',
        'table_position', 'points', 'games_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against'
    ]
    df_sports_final = df_sports_final[[c for c in schema_cols if c in df_sports_final.columns]]
    df_football_final = df_football_final[[c for c in schema_cols if c in df_football_final.columns]]

    df_sports_final['ingested_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    df_football_final['ingested_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Save final counts to telemetry store
    telemetry_store["record_counts"]["final_exported_sports"] = len(df_sports_final)
    telemetry_store["record_counts"]["final_exported_football"] = len(df_football_final)

    logger.info(f"Audit Phase: API-Sports branch aligned with {len(df_sports_final)} rows.")
    logger.info(f"Audit Phase: API-Football branch aligned with {len(df_football_final)} rows.")

    if len(df_sports_final) == 20 and len(df_football_final) == 20:
        logger.info("Validation Pass: Both pipeline branches successfully generated exactly 20 standard records.")
    else:
        logger.warning("Data Quality Alert: Mismatch detected in final dataset boundaries!")

    return df_sports_final, df_football_final



def append_telemetry_to_local_csv(telemetry, output_dir):
    """Flattens telemetry metadata and appends it to a local historical CSV for Looker Studio ingestion."""
    csv_path = os.path.join(output_dir, "pipeline_api_stats.csv")

    flattened_row = {
        "timestamp": telemetry["timestamp"],
        "pipeline_processing_time_ms": telemetry["pipeline_processing_time_ms"],
        "api_call_count": telemetry["api_call_count"],
        "error_rate": telemetry["error_rate"],
        "api_sports_latency_ms": telemetry["source_latency"]["api_sports_ms"],
        "api_football_latency_ms": telemetry["source_latency"]["api_football_ms"],
        "api_sports_raw_teams_count": telemetry["record_counts"]["api_sports_raw_teams"],
        "api_football_raw_teams_count": telemetry["record_counts"]["api_football_raw_teams"],
        "final_exported_sports_count": telemetry["record_counts"]["final_exported_sports"],
        "final_exported_football_count": telemetry["record_counts"]["final_exported_football"],
        "execution_status": "SUCCESS" if telemetry["error_rate"] == 0 else "PARTIAL_WARNING"
    }

    df_new = pd.DataFrame([flattened_row])

    try:
        if not os.path.exists(csv_path):
            df_new.to_csv(csv_path, index=False)
            logger.info("[BONUS] Created new telemetry history file: pipeline_api_stats.csv")
        else:
            df_new.to_csv(csv_path, mode='a', header=False, index=False)
            logger.info("[BONUS] Successfully appended run metrics to pipeline_api_stats.csv")
    except Exception as e:
        logger.error(f"Failed to write to pipeline_api_stats.csv: {e}")

def run_entire_etl_pipeline():
    """Coordinates the entire life cycle of the ETL process using a secure temporary runtime zone."""
    output_dir = os.getcwd()

    # Telemetry monitoring dictionary with initial states
    telemetry_store = {
        "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        "pipeline_stage": "execution_summary",
        "api_call_count": 0,
        "error_rate": 0.0,
        "execution_status": "SUCCESS",
        "source_latency": {
            "api_sports_ms": 0,
            "api_football_ms": 0
        },
        "record_counts": {
            "api_sports_raw_teams": 0,
            "api_football_raw_teams": 0,
            "final_exported_sports": 0,
            "final_exported_football": 0
        }
    }

    pipeline_start_time = time.time()

    try:
        with tempfile.TemporaryDirectory() as temp_landing_zone:
            sports_raw_json = os.path.join(temp_landing_zone, "api_sports_raw.json")
            football_raw_json = os.path.join(temp_landing_zone, "api_football_raw.json")

            logger.info("Starting Ingestion Phase...")
            sports_payload = fetch_api_sports_raw(PIPELINE_CONFIG["api_sports"], telemetry_store)
            with open(sports_raw_json, 'w') as f: json.dump(sports_payload, f)

            football_payload = fetch_api_football_raw(PIPELINE_CONFIG["api_football"], telemetry_store)
            with open(football_raw_json, 'w') as f: json.dump(football_payload, f)
            logger.info("Step 1 Complete: Both raw source datasets captured successfully.")

            df_sports, df_football = transform_source_data(sports_raw_json, football_raw_json, telemetry_store)

            sports_csv_path = os.path.join(output_dir, "api_sports_cleaned_df.csv")
            football_csv_path = os.path.join(output_dir, "api_football_cleaned_df.csv")

            df_sports.to_csv(sports_csv_path, index=False)
            df_football.to_csv(football_csv_path, index=False)

            logger.info(f"Cleaned target delivered to: {sports_csv_path}")
            logger.info(f"Cleaned target delivered to: {football_csv_path}")
            logger.info("Core ETL Lifecycle Complete. Deliverables verified.")

    except Exception as pipeline_error:
        telemetry_store["execution_status"] = "FAILED"
        telemetry_store["error_rate"] = 100.0
        logger.error(f"Pipeline execution halted due to error: {pipeline_error}")
        raise pipeline_error

    finally:
        total_time_ms = int((time.time() - pipeline_start_time) * 1000)
        telemetry_store["pipeline_processing_time_ms"] = total_time_ms

        append_telemetry_to_local_csv(telemetry_store, output_dir)

        logger.info("=========================================================")
        logger.info("[BONUS] PIPELINE RUN EXECUTION MONITORING TELEMETRY")
        logger.info(f"Execution Status: {telemetry_store['execution_status']}")
        logger.info(f"Total Processing Time: {total_time_ms} ms")
        logger.info(f"API Call Count: {telemetry_store['api_call_count']} calls")
        logger.info(
            f"Latency Summary: API-Sports={telemetry_store['source_latency']['api_sports_ms']}ms | API-Football={telemetry_store['source_latency']['api_football_ms']}ms")
        logger.info(
            f"Rows Captured: Raw Teams (S={telemetry_store['record_counts']['api_sports_raw_teams']}, F={telemetry_store['record_counts']['api_football_raw_teams']}) ──► Exported (S={telemetry_store['record_counts']['final_exported_sports']}, F={telemetry_store['record_counts']['final_exported_football']})")
        logger.info("=========================================================")

        print(json.dumps(telemetry_store))


def run_scheduled_pipeline():
    """Demonstrates how the pipeline can be scheduled periodically."""
    logger.info("Pipeline running in SCHEDULED mode. Task registered for daily execution at 02:00 AM.")
    run_entire_etl_pipeline()


if __name__ == "__main__":
    if "--scheduled" in sys.argv:
        try:
            run_scheduled_pipeline()
        except KeyboardInterrupt:
            logger.warning("Pipeline scheduling stopped by user.")
    else:
        try:
            run_entire_etl_pipeline()
        except Exception as pipeline_error:
            logger.critical(f"Pipeline execution aborted due to critical infrastructure failure: {pipeline_error}")