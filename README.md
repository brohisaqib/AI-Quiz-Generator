# AI Quiz Generator — Full-Stack Platform

A production-ready platform containing a **Flask backend API** and a **Streamlit frontend** designed to process educational source material (Videos, PDFs, or Search Topics) and generate structured, interactive multiple-choice quizzes complete with difficulty levels, topics, explanations, and automated G-Eval quality assessments.

---

## ─── Architecture & Pipeline Flow ───

The platform supports three pipeline entry points:

```mermaid
graph TD
    %% Inputs
    V[Video Upload] --> V_VAL[Validate Upload Size & MIME]
    P[PDF Upload] --> P_TXT[Extract Text via pdfplumber]
    T[Topic Input] --> T_DDG[Web Search via DuckDuckGo]
    
    %% Video stages
    V_VAL --> V_AUD[Extract Audio via MoviePy]
    V_AUD --> V_CHK[Split Audio into Chunks via Pydub]
    V_CHK --> V_TX[Speech-to-Text Transcription via Whisper]
    
    %% Intermediate texts
    V_TX --> MERGE[Consolidate Source Text]
    P_TXT --> MERGE
    T_DDG --> MERGE
    
    %% Generation Pipeline
    MERGE --> SUM[Generate Educational Summary via LLM]
    SUM --> QUIZ[Generate Structured MCQ Quiz via LLM]
    QUIZ --> GEVAL[Evaluate Quiz Quality via G-Eval Prompt]
    
    %% Persistence
    GEVAL --> DISK[Save to Outputs Folder as JSON/TXT]
    GEVAL --> SQLITE[Save Quiz Results to SQLite DB]
    
    %% Response
    DISK & SQLITE --> RES[Return Unified JSON Response]
```

---

## ─── Key Features ───

1. **JWT-Secured Admin Authentication**: Enforces stateless Bearer JWT token verification on all protected routes.
2. **Video-to-Quiz**: Extract WAV audio using `moviepy`, chunk into 10-minute MP3s with `pydub`, transcribe via Groq Whisper-large-v3, and construct quizzes.
3. **PDF-to-Quiz**: Parse selectable text from PDF documents using `pdfplumber`. Rejects scanned, non-textual, or image-only PDFs.
4. **Topic-to-Quiz**: Performs ad-hoc web searches via DuckDuckGo Search (no external developer API keys required) to curate source summaries and quizzes.
5. **G-Eval Assessment**: Automated prompt-based evaluation scoring (1–10) of the output questions for clarity, coverage, relevance, and accuracy.
6. **SQLite Storage**: Stores processed metadata and quiz JSON records in a file-backed SQLite database operating in WAL (Write-Ahead Logging) mode.
7. **Premium Streamlit UI**: Sleek, modern dark-mode portal with interactive exam player, summary tab, G-Eval reports, saved quizzes library, and downloads.

---

## ─── Folder Structure ───

```
AI-Quiz-Generator/
├── app/
│   ├── api/
│   │   ├── __init__.py          # Flask API blueprint definition
│   │   └── routes.py            # API routes (JWT-secured endpoints)
│   ├── config/
│   │   └── settings.py          # Configuration loading & validation
│   ├── models/
│   │   └── database.py          # SQLite database schema & CRUD helpers
│   ├── prompts/
│   │   ├── summary_prompt.py    # LLM instructions for summarizing text
│   │   ├── quiz_prompt.py       # LLM instructions for generating MCQs
│   │   └── evaluation_prompt.py # G-Eval prompt criteria
│   ├── schemas/
│   │   └── quiz.py              # Pydantic validation structures
│   ├── services/
│   │   ├── audio_service.py     # MoviePy extraction & Pydub chunking
│   │   ├── evaluation_service.py# G-Eval assessor
│   │   ├── pdf_service.py       # pdfplumber extractor
│   │   ├── quiz_service.py      # LLM MCQ orchestrator
│   │   ├── summary_service.py   # LLM summarizer
│   │   ├── upload_service.py    # File verification & storage
│   │   ├── web_search_service.py# DuckDuckGo search parser
│   │   └── whisper_service.py   # Groq Whisper API transcriber
│   ├── utils/
│   │   ├── auth.py              # Password hashing & JWT helper utilities
│   │   ├── helpers.py           # Filesystem cleanup & validation utilities
│   │   └── logger.py            # Centralized logger config
│   └── __init__.py              # Application factory
├── deploy/
│   └── AWS_DEPLOY.md            # Comprehensive EC2 deployment instructions
├── frontend/
│   └── app.py                   # Streamlit frontend application code
├── scripts/
│   └── generate_admin_password.py # Utility to generate hashed admin credentials
├── docker-compose.yml           # Multi-service production definition
├── Dockerfile.backend           # Flask image compilation recipe
├── Dockerfile.frontend          # Streamlit image compilation recipe
├── requirements.txt             # Project library requirements
└── README.md                    # This document
```

---

## ─── Environment Configuration (.env) ───

Copy `.env.example` to `.env` and configure:

```dotenv
# Flask
FLASK_APP=app.py
FLASK_ENV=development  # Set to "production" in Docker / AWS
PORT=5000

# API Keys
GROQ_API_KEY=gsk_your_groq_key
OPENAI_API_KEY=sk-proj-your_openai_key  # Optional fallback

# Admin Security Configuration
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=pbkdf2:sha256:260000$...  # Generate in Step 3
JWT_SECRET_KEY=your_random_jwt_secret_key    # Generate in Step 3
JWT_EXPIRY_HOURS=24
ALLOWED_ORIGINS=*

# Databases & Files
DATABASE_URL=postgresql://quizapp:your_password@localhost:5432/ai_quiz_generator
UPLOAD_FOLDER=uploads
TEMP_FOLDER=temp
OUTPUT_FOLDER=outputs
LOG_FOLDER=logs
MAX_UPLOAD_SIZE=104857600
```

---

## ─── Database Setup ───

Follow these manual steps to set up the PostgreSQL database (run these in your PostgreSQL client, e.g. `psql` or pgAdmin):

1. **Create the database and user, and grant privileges:**
   ```sql
   CREATE DATABASE ai_quiz_generator;
   CREATE USER quizapp WITH ENCRYPTED PASSWORD 'choose_a_strong_password';
   GRANT ALL PRIVILEGES ON DATABASE ai_quiz_generator TO quizapp;
   ```

2. **Connect to the database and grant schema privileges:**
   ```sql
   \c ai_quiz_generator
   GRANT ALL ON SCHEMA public TO quizapp;
   ```

3. **Run database migrations to create the tables:**
   After configuring the `DATABASE_URL` in your `.env` file (updating the password to your actual password), run:
   ```bash
   flask db upgrade
   ```

---

## ─── Running Locally (Without Docker) ───

### 1. Prerequisites
- Python 3.12+
- **FFmpeg** installed on your system path.
  * Windows: `choco install ffmpeg`
  * macOS: `brew install ffmpeg`
  * Linux: `sudo apt install ffmpeg`

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv venv
# Activate (Windows):
venv\Scripts\activate
# Activate (macOS/Linux):
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Generate Hashed Credentials & JWT Secrets
To secure the admin dashboard and protected backend routes:
```bash
# Generate the password hash for .env:
python scripts/generate_admin_password.py

# Generate a JWT Secret key:
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy these outputs into your `.env` file.

### 4. Start the Application
Run the backend API:
```bash
python app.py
```
Open a separate terminal window, activate the venv, and run the Streamlit frontend. The application is configured to resolve the `.env` path dynamically, so you can launch it from any directory:
```bash
# Option A: Launch from the project root directory
streamlit run frontend/app.py

# Option B: Launch from inside the frontend/ directory
cd frontend
streamlit run app.py
```
Visit `http://localhost:8501` to access the login page.

---

## ─── Running with Docker Compose ───

Initialize the services with a single command:
```bash
docker compose up -d --build
```
This builds and starts:
- **Backend API** (`http://localhost:5000`): Production Gunicorn server with FFmpeg.
- **Frontend App** (`http://localhost:8501`): Streamlit dashboard, configured automatically to route API calls via Docker's internal networks.

Check logs using:
```bash
docker compose logs -f
```

---

## ─── AWS Deployment ───

To deploy to AWS EC2:
1. Spin up an **Ubuntu 22.04 LTS** instance (`t3.small` recommended with 20+ GB storage).
2. Configure **Security Group** rules to expose TCP ports `22` (SSH), `5000` (Backend API), and `8501` (Streamlit portal).
3. Follow the detailed steps in [AWS_DEPLOY.md](file:///deploy/AWS_DEPLOY.md) to set up Docker, check out code, configure environment variables, and launch production containers under Docker Compose.

---

## ─── API endpoints ───

All endpoints except `/health` and `/admin/login` require the header:
`Authorization: Bearer <JWT_TOKEN>`

### 1. `POST /admin/login`
- **Body**: `{"username": "admin", "password": "your_password"}`
- **Response**: `{"success": true, "token": "...", "expires_in_hours": 24}`

### 2. `POST /generate-quiz-from-pdf`
- **Body**: `multipart/form-data` with `file` containing the PDF binary.
- **Response**: Canonical quiz JSON structure containing title, summary, questions array, and evaluation score.

### 3. `POST /generate-quiz-from-topic`
- **Body**: `{"topic": "Artificial Intelligence", "max_results": 5}`
- **Response**: Canonical quiz JSON.

### 4. `GET /quiz/<id>`
- **Response**: Returns saved quiz JSON.
