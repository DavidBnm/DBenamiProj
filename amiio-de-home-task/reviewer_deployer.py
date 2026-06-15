#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import json
import argparse
import requests
import re
import getpass

# ANSI escape codes for beautiful formatting
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log_info(message):
    print(f"{Colors.BLUE}[INFO]{Colors.ENDC} {message}")

def log_success(message):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.ENDC} {Colors.BOLD}{message}{Colors.ENDC}")

def log_warn(message):
    print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {message}")

def log_error(message):
    print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {Colors.BOLD}{message}{Colors.ENDC}")

def sanitize_name(name):
    """Sanitizes names for files and GitHub repos (alphanumeric and hyphens only)."""
    s = name.lower()
    s = re.sub(r'[^a-z0-9\-]', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')

def scan_assignment_dir(source_dir):
    """Scans the source directory for code files, returning a list of scanned file objects."""
    scanned_files = {}
    ignored_patterns = [
        r'\.git$', r'\.git/', r'__pycache__', r'\.DS_Store', 
        r'\.venv', r'venv', r'env', r'\.idea', r'\.vscode', r'\.egg-info'
    ]
    
    text_extensions = {
        '.py', '.sql', '.json', '.yaml', '.yml', '.md', '.txt', '.sh', '.ini', '.cfg', '.ipynb'
    }
    
    log_info(f"Scanning directory: {source_dir}")
    for root, dirs, files in os.walk(source_dir):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if not any(re.search(pat, os.path.join(root, d)) for pat in ignored_patterns)]
        
        for file in files:
            file_path = os.path.join(root, file)
            # Skip if path matches any ignored pattern
            if any(re.search(pat, file_path) for pat in ignored_patterns):
                continue
                
            rel_path = os.path.relpath(file_path, source_dir)
            _, ext = os.path.splitext(file)
            
            # Skip binary files or non-code files by reading size and check extensions
            file_size = os.path.getsize(file_path)
            if ext.lower() not in text_extensions or file_size > 100 * 1024:
                # Do not scan large text files or non-code extensions, but log them
                log_info(f"Skipping content read for {rel_path} (size: {file_size} bytes, type: {ext})")
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    scanned_files[rel_path] = content
            except Exception as e:
                log_warn(f"Could not read file {rel_path}: {e}")
                
    log_success(f"Scanned {len(scanned_files)} file(s) successfully.")
    return scanned_files

def call_gemini_api(api_key, model_name, company, role, files_content):
    """Calls the Gemini API to analyze, optimize, and generate the README."""
    log_info(f"Invoking Gemini API ({model_name}) for code analysis and optimization...")
    
    # Format the files content for the prompt
    formatted_files = ""
    for path, content in files_content.items():
        formatted_files += f"\n--- START FILE: {path} ---\n{content}\n--- END FILE: {path} ---\n"
        
    prompt = f"""You are a Senior Data Engineer, Principal Software Architect, and Hiring Manager.
We are reviewing a candidate's Home Assignment for:
- Company Name: {company}
- Target Role: {role}

Below are the home assignment code files:
{formatted_files}

Perform the following tasks:
1. Review the files for code quality, SQL query efficiency, pipeline design, logging, error handling, modularity, scalability, and clean data engineering practices. Write a detailed review summary in Markdown.
2. Generate the complete optimized/refactored version of the core script(s) or queries where improvement is needed. Focus on adding robust logging, error handling, clean configuration parameters, docstrings, typing, or optimizing query performance. Do not output code placeholders.
3. Generate a highly professional, enterprise-grade README.md file tailored specifically for the hiring managers, explaining the architecture, setup instructions, and design choices.

Respond with a JSON object that matches the following structure:
{{
  "review_summary": "Your detailed code review summary in Markdown.",
  "optimized_files": {{
     "path/to/file.py": "Complete content of the optimized file..."
  }},
  "readme_content": "Complete Markdown content for the README.md file."
}}

Make sure the keys in 'optimized_files' match the exact relative path of the original files you are optimizing. If a file does not need optimization, do not include it in 'optimized_files'.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "review_summary": {
                        "type": "STRING",
                        "description": "A detailed, professional code review of the input files focusing on code quality, SQL efficiency, and pipeline design."
                    },
                    "optimized_files": {
                        "type": "OBJECT",
                        "description": "A mapping of relative file paths to their fully optimized code content.",
                        "additionalProperties": {
                            "type": "STRING"
                        }
                    },
                    "readme_content": {
                        "type": "STRING",
                        "description": "The complete README.md content tailored for hiring managers."
                    }
                },
                "required": ["review_summary", "optimized_files", "readme_content"]
            }
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            log_error(f"Gemini API returned status code {response.status_code}")
            log_error(f"Response: {response.text}")
            sys.exit(1)
            
        res_data = response.json()
        
        # Extract response text
        try:
            raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError) as e:
            log_error(f"Failed to parse text from Gemini response: {e}")
            log_error(f"Response structure: {res_data}")
            sys.exit(1)
            
        # Parse text as JSON
        try:
            # Clean markdown code fences if Gemini returned them despite responseMimeType
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            result = json.loads(cleaned_text)
            return result
        except json.JSONDecodeError as e:
            log_error(f"Failed to decode response text as JSON: {e}")
            log_error(f"Raw text response:\n{raw_text}")
            sys.exit(1)
            
    except Exception as e:
        log_error(f"HTTP request to Gemini API failed: {e}")
        sys.exit(1)

def build_optimized_workspace(source_dir, output_dir, gemini_result):
    """Replicates source directory to output directory, updates optimized files, and adds README.md."""
    log_info(f"Building optimized workspace in: {output_dir}")
    
    # 1. Clean and create output directory
    if os.path.exists(output_dir):
        log_warn(f"Target directory {output_dir} already exists. Recreating it...")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Copy all files from source to output
    log_info("Copying files from source directory...")
    ignored_patterns = [
        r'\.git$', r'\.git/', r'__pycache__', r'\.DS_Store', 
        r'\.venv', r'venv', r'env', r'\.idea', r'\.vscode', r'\.egg-info'
    ]
    
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not any(re.search(pat, os.path.join(root, d)) for pat in ignored_patterns)]
        for file in files:
            file_path = os.path.join(root, file)
            if any(re.search(pat, file_path) for pat in ignored_patterns):
                continue
                
            rel_path = os.path.relpath(file_path, source_dir)
            target_path = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(file_path, target_path)
            
    # 3. Apply optimized files
    log_info("Applying optimizations from Gemini API...")
    optimized_files = gemini_result.get("optimized_files", {})
    for path, content in optimized_files.items():
        target_path = os.path.join(output_dir, path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            log_success(f"Optimized file written: {path}")
        except Exception as e:
            log_error(f"Could not write optimized file {path}: {e}")
            
    # 4. Write README.md
    readme_path = os.path.join(output_dir, "README.md")
    readme_content = gemini_result.get("readme_content", "")
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        log_success("README.md written successfully.")
    except Exception as e:
        log_error(f"Could not write README.md: {e}")

def create_github_repo(username, token, repo_name, private=True):
    """Creates a remote repository on GitHub using the REST API."""
    log_info(f"Creating GitHub repository '{repo_name}' on account '{username}'...")
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    payload = {
        "name": repo_name,
        "description": f"Home Assignment - Optimized production-grade architecture.",
        "private": private,
        "auto_init": False
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            log_success(f"Successfully created GitHub repository: {repo_name}")
            return True
        elif response.status_code == 422:
            # 422 usually indicates the repo already exists
            log_warn(f"GitHub repository '{repo_name}' might already exist. Attempting to push to existing repository...")
            return True
        else:
            log_error(f"Failed to create GitHub repository. Status code: {response.status_code}")
            log_error(f"Response: {response.text}")
            return False
    except Exception as e:
        log_error(f"Error calling GitHub API: {e}")
        return False

def deploy_to_github(repo_dir, username, token, repo_name):
    """Initializes local Git repo and pushes it to GitHub using subprocesses."""
    log_info("Deploying to GitHub...")
    
    # helper for running git commands
    def run_git(args, check=True):
        cmd = ["git"] + args
        result = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0 and check:
            log_error(f"Git command failed: {' '.join(cmd)}")
            log_error(f"Stdout: {result.stdout}")
            log_error(f"Stderr: {result.stderr}")
            raise RuntimeError(result.stderr)
        return result

    try:
        # Check if already a git repo, if so, clean it
        if os.path.exists(os.path.join(repo_dir, ".git")):
            log_warn("Local Git repository already exists in target directory. Re-initializing...")
            shutil.rmtree(os.path.join(repo_dir, ".git"))

        # 1. Init repo
        run_git(["init"])
        
        # Set branch name to main
        run_git(["checkout", "-b", "main"], check=False)
        run_git(["branch", "-M", "main"], check=False)
        
        # 2. Check/configure user credentials (to prevent commit failure)
        name_check = run_git(["config", "user.name"], check=False)
        email_check = run_git(["config", "user.email"], check=False)
        
        if not name_check.stdout.strip():
            log_info(f"Setting local git user.name to '{username}'")
            run_git(["config", "user.name", username])
        if not email_check.stdout.strip():
            log_info(f"Setting local git user.email to '{username}@users.noreply.github.com'")
            run_git(["config", "user.email", f"{username}@users.noreply.github.com"])
            
        # 3. Add authenticated remote
        # Structure requested: https://DavidBnm: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@github.com/DavidBnm/{repo_name}.git
        remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
        run_git(["remote", "add", "origin", remote_url])
        
        # 4. Stage, commit, and push
        run_git(["add", "."])
        run_git(["commit", "-m", "Initial commit: Optimized production-grade architecture"])
        
        log_info(f"Pushing to remote repository: https://github.com/{username}/{repo_name}.git")
        run_git(["push", "-u", "origin", "main"])
        
        log_success("Code successfully pushed to GitHub!")
        return f"https://github.com/{username}/{repo_name}"
        
    except Exception as e:
        log_error(f"Failed to deploy repository to GitHub: {e}")
        return None

MOCK_GEMINI_RESULT = {
    "review_summary": """# Code Review & Optimization Summary

## 1. Code Quality & Best Practices
- **Logging vs Printing**: Replaced standard `print` statements with Python's built-in `logging` module to support production-level tracking and debugging.
- **Exception Handling**: Added try-except blocks around file reads and database writes to prevent silent pipeline crashes.
- **Resource Management**: Implemented context managers (`with` statements) for database connections to ensure connections are properly closed even if errors occur.

## 2. SQL Query Efficiency
- **SELECT * Avoidance**: Replaced `SELECT *` with explicit column selection to minimize data transfer overhead.
- **Query Structure**: Substituted the inefficient `IN (subquery)` clause with an optimized `INNER JOIN` construct, enabling the database query optimizer to execute it efficiently using indexes.

## 3. Architecture & Edge-case Handling
- **Modularity**: Structured code into logical functions with type hints and clear docstrings.
- **Parameterization**: Externalized hardcoded DB paths and configuration settings.
""",
    "optimized_files": {
        "test_pipeline.py": """import logging
import sqlite3
import pandas as pd
from typing import Optional
import sys

# Setup production logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_data(file_path: str) -> pd.DataFrame:
    \"\"\"Loads data from a CSV file.
    
    Args:
        file_path: Path to the CSV source.
        
    Returns:
        pd.DataFrame containing the loaded data.
    \"\"\"
    logger.info("Loading data from %s...", file_path)
    try:
        df = pd.read_csv(file_path)
        logger.info("Successfully loaded %d rows.", len(df))
        return df
    except FileNotFoundError as e:
        logger.error("Source file not found: %s", file_path)
        raise e
    except Exception as e:
        logger.error("Failed to load data: %s", str(e))
        raise e

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    \"\"\"Cleans columns in the dataframe.
    
    Args:
        df: Input DataFrame.
        
    Returns:
        Cleaned DataFrame.
    \"\"\"
    logger.info("Cleaning and normalizing data columns...")
    df = df.copy()
    if 'email' in df.columns:
        df['email'] = df['email'].astype(str).str.strip().str.lower()
    return df

def save_to_db(df: pd.DataFrame, db_path: str, table_name: str) -> None:
    \"\"\"Saves dataframe to the target SQLite table.
    
    Args:
        df: DataFrame to save.
        db_path: Path to SQLite DB.
        table_name: Destination table name.
    \"\"\"
    logger.info("Saving data to DB table '%s'...", table_name)
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # Use transaction control
        with conn:
            df.to_sql(table_name, conn, if_exists='replace', index=False)
        logger.info("Successfully saved data to database.")
    except sqlite3.Error as e:
        logger.error("Database error occurred: %s", str(e))
        raise e
    finally:
        if conn:
            conn.close()

def main():
    db_path = 'my_data.db'
    source_file = 'data.csv'
    table_name = 'users'
    
    try:
        data = load_data(source_file)
        cleaned = clean_data(data)
        save_to_db(cleaned, db_path, table_name)
        logger.info("Data pipeline executed successfully.")
    except Exception as e:
        logger.critical("Data pipeline execution failed: %s", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
        "test_query.sql": """-- Optimized SQL Query
-- Replaced SELECT * with explicit columns to optimize network and disk I/O.
-- Converted inefficient IN subquery to INNER JOIN to leverage indexes.
SELECT 
    o.order_id,
    o.user_id,
    o.order_date,
    o.total_amount
FROM orders o
INNER JOIN users u ON o.user_id = u.user_id
WHERE u.country = 'United States'
  AND o.order_date > '2023-01-01'
ORDER BY o.order_date DESC;
"""
    },
    "readme_content": """# Wix - Data Engineer Home Assignment

Enterprise-grade, optimized production pipeline submission.

## Architecture

This pipeline reads raw data, cleans customer email information (normalizing spacing and casing), and loads it into a relational SQLite database structure.

### Key Enhancements Added

1. **Robust Production Logging**: Replaced print statements with structured logger outputs.
2. **Proper Connection Handling**: Implemented context managers to avoid resource leaks.
3. **Optimized DB Access**: Refactored SQL queries to use `INNER JOIN` rather than `IN` subqueries for efficient execution planning.
4. **Type Safety & Modularity**: Added clear PEP 8 standard docstrings and type hints.

## Setup Instructions

1. Ensure Python 3.8+ is installed.
2. Install dependencies:
   ```bash
   pip install pandas
   ```
3. Run the pipeline:
   ```bash
   python test_pipeline.py
   ```
"""
}

def main():
    parser = argparse.ArgumentParser(description="Home Assignment Reviewer & Deployer")
    parser.add_argument("--assignment-dir", required=True, help="Path to local directory containing home assignment")
    parser.add_argument("--company", required=True, help="Target company name (e.g. Wix)")
    parser.add_argument("--role", required=True, help="Target role (e.g. Data Engineer)")
    parser.add_argument("--output-dir", help="Path to write the optimized assignment (defaults to company_home_assignment_optimized)")
    parser.add_argument("--gemini-api-key", help="Gemini API Key (defaults to GEMINI_API_KEY env var)")
    parser.add_argument("--github-token", default="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", help="GitHub Personal Access Token")
    parser.add_argument("--github-username", default="DavidBnm", help="GitHub Username")
    parser.add_argument("--public", action="store_true", help="Create a public repository (defaults to private)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini Model version to use")
    parser.add_argument("--mock", action="store_true", help="Use mock Gemini API response for local/offline testing")
    
    args = parser.parse_args()
    
    # 1. Validation
    source_dir = os.path.abspath(args.assignment_dir)
    if not os.path.exists(source_dir) or not os.path.isdir(source_dir):
        log_error(f"Source assignment directory does not exist or is not a directory: {source_dir}")
        sys.exit(1)
        
    # Get Gemini API key (only if not mocking)
    api_key = None
    if not args.mock:
        api_key = args.gemini_api_key
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")
            
        if not api_key:
            log_warn("Gemini API Key not found in command line arguments or environment variable GEMINI_API_KEY.")
            api_key = getpass.getpass("Enter your Gemini API Key: ").strip()
            if not api_key:
                log_error("Gemini API Key is required to proceed.")
                sys.exit(1)
            
    # Set default output directory
    clean_company_name = sanitize_name(args.company)
    if not args.output_dir:
        output_dir = os.path.abspath(f"{clean_company_name}_home_assignment_optimized")
    else:
        output_dir = os.path.abspath(args.output_dir)
        
    repo_name = f"{clean_company_name}-home-assignment"
    
    print("\n" + "="*60)
    print(f"{Colors.HEADER}{Colors.BOLD}Home Assignment Reviewer & Deployer{Colors.ENDC}")
    print(f"Company:      {args.company}")
    print(f"Role:         {args.role}")
    print(f"Source Dir:   {source_dir}")
    print(f"Output Dir:   {output_dir}")
    print(f"GitHub Repo:  https://github.com/{args.github_username}/{repo_name}")
    print("="*60 + "\n")
    
    # 2. Scan Files
    scanned_files = scan_assignment_dir(source_dir)
    if not scanned_files:
        log_error("No readable code/text files found in source assignment directory.")
        sys.exit(1)
        
    # 3. Call Gemini API
    if args.mock:
        log_info("Using mock Gemini API response...")
        result = MOCK_GEMINI_RESULT
    else:
        result = call_gemini_api(api_key, args.model, args.company, args.role, scanned_files)
    
    # 4. Save review and apply changes
    build_optimized_workspace(source_dir, output_dir, result)
    
    # 5. Create remote GitHub Repository
    is_created = create_github_repo(args.github_username, args.github_token, repo_name, private=not args.public)
    
    # 6. Deploy to GitHub
    repo_url = None
    if is_created:
        repo_url = deploy_to_github(output_dir, args.github_username, args.github_token, repo_name)
        
    # 7. Print output summary
    print("\n" + "="*60)
    print(f"{Colors.HEADER}{Colors.BOLD}Code Review & Optimization Summary:{Colors.ENDC}")
    print("="*60)
    print(result.get("review_summary", "No summary provided."))
    print("="*60)
    
    if repo_url:
        print(f"\n{Colors.GREEN}{Colors.BOLD}DEPLOYMENT SUCCESSFUL!{Colors.ENDC}")
        print(f"Direct GitHub Link: {Colors.UNDERLINE}{repo_url}{Colors.ENDC}\n")
    else:
        log_error("Deployment failed. Please check local git logs or GitHub API logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
