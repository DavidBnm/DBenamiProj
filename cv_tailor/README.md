# CV Tailoring & Outreach Agent

An automated, ATS-oriented Python agent that processes job descriptions, aligns your professional summary and experience bullet points (without fabrication), and builds customized LinkedIn messages.

---

## Project Structure

```text
cv_tailor/
├── README.md
├── requirements.txt
├── .env.example
├── config.py
├── main.py
├── master_cv.md          # Candidate's master CV
├── tailored_cvs/         # Output directory for tailored markdown CVs
└── outreach_messages/    # Output directory for outreach text files
```

---

## Getting Started

### 1. Installation
Create and activate a virtual environment, then install requirements:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Setup
Configure your API credentials:
```bash
cp .env.example .env
```

Edit `.env` and supply your Gemini API key:
```ini
# Gemini API Configuration
GEMINI_API_KEY=your_actual_gemini_api_key
```

*Note: If no API key is provided, the script gracefully falls back to a rules-based parser to verify pipeline performance locally without errors.*

---

## How to Run

1. Place your target Job Description text in a local text file (e.g. `jd_abra.txt`).
2. Run the main entry point, specifying the company name and path to the Job Description file:

```bash
python main.py --company "Abra" --jd-file "/path/to/jd_abra.txt"
```

### Execution Parameters
- `--company` (Required): Name of the hiring firm. Used for naming outputs and context.
- `--jd-file` (Required): Path to the text file containing the job description.
- `--cv-dir` (Optional, defaults to `tailored_cvs`): Output folder for the tailored CVs.
- `--message-dir` (Optional, defaults to `outreach_messages`): Output folder for tailored LinkedIn outreach messages.

### Outputs Generated
- A tailored CV in markdown format stored at `tailored_cvs/cv_{company_name}.md` with your profile summary and experience bullet points optimized for the JD.
- A 3-4 sentence targeted LinkedIn outreach message saved at `outreach_messages/message_{company_name}.txt`.
