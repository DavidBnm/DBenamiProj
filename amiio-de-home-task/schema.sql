-- Source Provider A: API-Sports Data Asset Ledger
CREATE TABLE IF NOT EXISTS premier_league_teams_sports (
    team_id          VARCHAR(50)  PRIMARY KEY, -- Unique identifier from the source API
    team_name        VARCHAR(100) NOT NULL,    -- Official standardized name of the football club
    founded_year     INT,                      -- The year the club was established
    stadium_name     VARCHAR(150),             -- Name of the team's home stadium
    city             VARCHAR(100),             -- City where the club/stadium is located
    season           INT          NOT NULL,    -- The year of the season (e.g., 2024)
    table_position   INT          NOT NULL,    -- Current rank in the league standings
    points           INT          NOT NULL,    -- Total points accumulated in the season
    games_played     INT          NOT NULL,    -- Total matches played so far
    wins             INT          NOT NULL,    -- Number of matches won
    draws            INT          NOT NULL,    -- Number of matches ended in a tie
    losses           INT          NOT NULL,    -- Number of matches lost
    goals_for        INT          NOT NULL,    -- Total goals scored by the team (GF)
    goals_against    INT          NOT NULL,    -- Total goals conceded by the team (GA)
    ingested_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP -- Audit timestamp of the pipeline run
);

-- Source Provider B: API-Football Data Asset Ledger
CREATE TABLE IF NOT EXISTS premier_league_teams_football (
    team_id          VARCHAR(50)  PRIMARY KEY,
    team_name        VARCHAR(100) NOT NULL,
    founded_year     INT,
    stadium_name     VARCHAR(150),
    city             VARCHAR(100),
    season           INT          NOT NULL,
    table_position   INT          NOT NULL,
    points           INT          NOT NULL,
    games_played     INT          NOT NULL,
    wins             INT          NOT NULL,
    draws            INT          NOT NULL,
    losses           INT          NOT NULL,
    goals_for        INT          NOT NULL,
    goals_against    INT          NOT NULL,
    ingested_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- Central Infrastructure Operational Telemetry Log
CREATE TABLE IF NOT EXISTS pipeline_telemetry (
    timestamp                    TIMESTAMP    PRIMARY KEY, -- Epoch pinpointing pipeline execution
    pipeline_processing_time_ms  INT          NOT NULL,    -- Duration of complete ETL lifecycle
    api_call_count               INT          NOT NULL,    -- Quantitative metric tracing API workloads
    error_rate                   FLOAT        NOT NULL,    -- Tracked ratio of unfulfilled requests
    api_sports_latency_ms        INT          NOT NULL,    -- Network performance tracing for API-Sports
    api_football_latency_ms      INT          NOT NULL,    -- Network performance tracing for API-Football
    execution_status             VARCHAR(50)  NOT NULL     -- State validation parameter (SUCCESS/FAILED)
);