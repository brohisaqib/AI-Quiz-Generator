# PROJECT_DOCUMENTATION.md

## 1. TECH STACK
Is project mein ye technologies aur libraries actually use hui hain:

**Backend framework**
- Flask: Ye main backend framework hai jo APIs ko host karne aur requests ko handle karne ke liye use hota hai.
- Flask-CORS: Ye frontend (Streamlit ya SPA) se aane wali cross-origin requests ko allow karne ke liye use hota hai.
- Flask-Limiter: Ye brute-force attacks ko rokne ke liye rate limiting provide karta hai (e.g. `/auth/login` par).

**Database & ORM**
- PostgreSQL: Ye main relational database hai jahan users, quizzes, aur refresh tokens ka data save hota hai.
- SQLAlchemy: Ye Python ka ORM hai jo database tables ko Python classes mein map karne aur queries likhne ke liye use hota hai.
- Flask-SQLAlchemy & Flask-Migrate: Ye Flask ke andar SQLAlchemy ko integrate karne aur database migrations ko manage karne ke liye use hote hain.
- Alembic: Ye database schema changes ko apply karne (migrations) ke liye background mein kaam karta hai.

**Authentication**
- PyJWT: Ye JSON Web Tokens (JWT) generate aur verify karne ke liye use hota hai taake users securely authenticate ho sakein.
- Werkzeug: Iski `generate_password_hash` aur `check_password_hash` utilities user passwords ko securely encrypt/verify karne ke liye use hoti hain.

**AI/LLM provider(s) and specific models used**
- Groq: Ye main LLM provider hai jo fast inference ke liye use ho raha hai.
- langchain-groq: Ye LangChain ka integration hai jo ChatGroq ko use karke LLM calls karta hai.
- Llama-3 (llama-3.1-8b-instant): Ye model text summary aur quiz generation ke liye use hota hai.
- Whisper (whisper-large-v3): Ye model Groq ke through audio transcription ke liye use hota hai.
- OpenAI: Code mein `openai` library imported hai lekin mostly Groq ka base URL (`https://api.groq.com/openai/v1`) use karke OpenAI-compatible endpoints access kiye jate hain.

**Audio/video/PDF processing libraries**
- MoviePy: Ye uploaded video file se audio track extract karne ke liye use hota hai.
- Pydub: Ye extracted audio ko chote chunks mein split karne ke liye use hota hai taake Whisper API ki size limits cross na hon.
- pdfplumber: Ye uploaded PDF documents se text extract karne ke liye use hota hai.

**Frontend framework**
- HTML/JS/CSS (Vanilla): `frontend/static` mein SPA (Single Page Application) bani hui hai.
- Flask (Frontend server): `frontend/app.py` mein ek chota Flask server hai jo in static files ko serve karta hai.
- Streamlit: `requirements.txt` aur `docker-compose.yml` mein mention hai, lekin existing code dekh kar lagta hai ke custom static frontend (JS) bhi exist karta hai.

**Deployment/containerization tools**
- Docker & Docker Compose: Ye backend, frontend, aur PostgreSQL database ko containers mein run karne aur environments ko isolate karne ke liye use hote hain.
- Gunicorn: Ye production server hai jo backend Flask app ko host karne ke liye use hota hai.

## 2. COMPLETE FILE STRUCTURE
```text
/
├── Dockerfile.backend        # Backend API ko containerize karne ke instructions
├── Dockerfile.frontend       # Frontend app ko containerize karne ke instructions
├── README.md                 # Project ka basic overview aur setup guide
├── app.py                    # App initialize aur run karne ka main entry point (mostly dev ke liye)
├── docker-compose.prod.yml   # Production environment ke liye Docker services ki configuration
├── docker-compose.yml        # Local development ke liye Docker services ki configuration
├── project_audit.md          # Project ka audit ya planning document
├── requirements.txt          # Python dependencies ki list jo install karni hoti hain
├── wsgi.py                   # Production mein Gunicorn ke sath app run karne ka entry point
├── .dockerignore             # Docker build mein jin files/folders ko ignore karna hai unki list
├── .env.example              # Environment variables ka template file
├── .gitignore                # Git mein jin files/folders ko ignore karna hai unki list
├── app/
│   ├── __init__.py           # Flask app factory aur database initialization ka logic
│   ├── api/
│   │   ├── __init__.py       # Blueprint register karne ki file
│   │   ├── auth_routes.py    # Signup, login, logout, aur token refresh ke endpoints
│   │   └── routes.py         # Quiz generation (video/PDF/topic) aur retrieval ke endpoints
│   ├── config/
│   │   ├── __init__.py       # Config package initialization
│   │   └── settings.py       # Environment variables load aur validate karne wali Config class
│   ├── core/
│   │   ├── __init__.py       # Core package initialization
│   │   └── exceptions.py     # Custom error classes (jaise OpenAIServiceError)
│   ├── models/
│   │   ├── __init__.py       # SQLAlchemy db object aur models export karne ki file
│   │   ├── quiz_result.py    # Quiz results store karne ka database model
│   │   ├── refresh_token.py  # JWT refresh tokens ko secure rakhne ka model
│   │   ├── user.py           # User accounts store karne ka database model
│   │   └── video_job.py      # Uploaded files ki job tracking ka model
│   ├── prompts/
│   │   ├── __init__.py       # Prompts package initialization
│   │   ├── evaluation_prompt.py # Quiz ko evaluate karne ka LangChain prompt
│   │   ├── quiz_prompt.py    # Summary se quiz generate karne ka LangChain prompt
│   │   └── summary_prompt.py # Transcript/text se summary bananeka LangChain prompt
│   ├── schemas/
│   │   ├── __init__.py       # Schemas package initialization
│   │   └── quiz.py           # Pydantic models jo LLM output ko structure karte hain
│   ├── services/
│   │   ├── __init__.py       # Services package initialization
│   │   ├── audio_service.py  # Video se audio extract aur chunk karne ka logic
│   │   ├── evaluation_service.py # LLM ke zariye quiz quality evaluate karne ka logic
│   │   ├── pdf_service.py    # PDF se text extract karne ka logic
│   │   ├── quiz_service.py   # Text se multiple choice questions banane ka logic
│   │   ├── summary_service.py # Text ya transcript ko summarize karne ka logic
│   │   ├── upload_service.py # Uploaded files ko validate aur save karne ka logic
│   │   ├── web_search_service.py # DuckDuckGo/Google se topic search karke text lane ka logic
│   │   └── whisper_service.py # Audio chunks ko Groq Whisper ke zariye transcribe karne ka logic
│   ├── templates/            # Empty folder, shayad email ya HTML templates ke liye
│   └── utils/
│       ├── __init__.py       # Utils package initialization
│       ├── auth.py           # JWT generation, verification, aur @require_auth decorator
│       ├── helpers.py        # Choti utilities jese file delete karne ka function
│       ├── logger.py         # Standard logging setup karne ka module
│       ├── openai_error_handler.py # OpenAI/Groq errors ko catch aur format karne ka logic
│       └── validators.py     # Inputs (jese email ya password) validate karne ke functions
└── frontend/
    ├── app.py                # Frontend static files serve karne ka Flask server
    ├── auth_utils.py         # Frontend ke liye authentication utilities
    └── static/
        ├── app.js            # SPA ka main JavaScript code jo backend se API calls karta hai
        ├── index.html        # Main HTML layout aur UI
        └── style.css         # UI ki styling aur colors
```

## 3. WHAT EACH FILE ACTUALLY DOES (detailed)

**app.py (Root)**
System mein is file ki responsibility development server ko run karna hai. Ye file `app` folder se `create_app()` function import karti hai aur Flask app object banati hai. Isko directly run karne se backend local port par start ho jata hai. Ek naye developer ko pata hona chahiye ke ye production mein use nahi hoti, wahan `wsgi.py` kaam aati hai.

**wsgi.py**
Ye file production environment mein Gunicorn server ke liye entry point ka kaam karti hai. Ye bhi `create_app()` call karke app object initialize karti hai jisko Gunicorn serve karta hai. Isme koi logic nahi hoti, bas application instance ko expose karti hai.

**app/__init__.py**
Is file ka main kaam Flask application ki factory create karna aur saare extensions (SQLAlchemy, Migrate, CORS, Limiter) ko initialize karna hai. Yehi routes (blueprints) ko register karti hai aur database models ko import karti hai taake SQLAlchemy unhe pehchan sake. Ek important behavior ye hai ke ye `settings.py` se configuration load karti hai app start hone se pehle.

**app/api/auth_routes.py**
Ye file user authentication ke saare API endpoints define karti hai. Isme `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, aur `/auth/me` jaise routes maujood hain. Ye file `app.utils.auth` se JWT functions import karti hai aur passwords verify karke tokens generate karti hai. Isme login route par Flask-Limiter se rate limiting bhi apply ki gayi hai taake brute force attacks na ho sakein.

**app/api/routes.py**
Ye backend ki sab se bari aur important file hai jo quiz generation ka poora end-to-end pipeline control karti hai. Isme `/upload-video`, `/generate-quiz`, `/generate-quiz-from-pdf`, aur `/generate-quiz-from-topic` ke endpoints hain. Ye file saari services (AudioService, WhisperService, QuizService waghera) ko sequentially call karke final quiz JSON banati hai aur database mein save karti hai. Is file mein error handling aur files ko process hone ke baad delete (cleanup) karne ka behavior bohot critical hai.

**app/config/settings.py**
Is file ki responsibility `.env` file se environment variables ko load karna aur application ke liye ek `Config` class banana hai. Ye database URL, API keys, folder paths, aur JWT secrets store karti hai. Isme class methods bhi hain (`ensure_directories_exist`, `validate_database_config`) jo app start hone par check karte hain ke zaroori folders bane hue hain aur config theek hai ya nahi.

**app/core/exceptions.py**
Ye file custom exception classes define karti hai jo poori app mein error handling ke liye use hoti hain. Maslan `OpenAIServiceError` class banai gayi hai taake AI API ke fails hone par proper status code aur message set kiya ja sake. Ye services ko API ke errors ko uniform tareeqe se route tak pohanchane mein madad karti hai.

**app/models/quiz_result.py**
Ye SQLAlchemy model define karti hai jo generated quizzes ko database mein `quiz_results` table mein save karta hai. Isme quiz ka title, summary, JSON format mein questions, aur evaluation score store hota hai. Ye foreign keys ke zariye `User` aur `VideoJob` models se connect hota hai.

**app/models/refresh_token.py**
Ye file `refresh_tokens` table ka schema define karti hai jo users ki session security ke liye zaroori hai. Isme JWT refresh token ka sirf hash save hota hai, asli token nahi, taake database leak hone par tokens safe rahein. Ye expiry date aur 'revoked' status bhi rakhti hai taake user logout kar sake.

**app/models/user.py**
Ye file `users` table ka schema banati hai jisme username, email, aur password hash store hote hain. Ye system ka core identity model hai jisko authentication routes import karke check karte hain. Isme relations define kiye gaye hain taake ek user ke saare video jobs aur quizzes fetch kiye ja sakein.

**app/models/video_job.py**
Ye model us file ya topic ka record rakhta hai jiske through quiz generate kiya gaya. Isme original filename, stored path, aur source type ("video", "pdf", ya "topic") save hota hai. Ye `QuizResult` se linked hota hai aur batata hai ke quiz kis source se bana tha.

**app/prompts/evaluation_prompt.py, quiz_prompt.py, summary_prompt.py**
Ye files LangChain ki `PromptTemplate` objects define karti hain. Inka maqsad LLM ko exact instructions dena hai ke transcript se summary kaise banani hai, summary se quiz kaise banani hai, aur phir us quiz ko evaluate kaise karna hai. In files mein system instructions aur few-shot examples (agar hon) likhe hote hain.

**app/schemas/quiz.py**
Ye file Pydantic models (`QuizQuestion`, `QuizResponse`, `QuizEvaluation`) define karti hai. Iska maqsad Groq LLM se aane wale raw JSON output ko validate karna aur enforce karna hai ke har question ka option aur answer sahi structure mein ho. Ye `QuizService` aur `EvaluationService` dono mein import hoti hai.

**app/services/audio_service.py**
Ye service uploaded video file se audio track extract karne aur usko chunks mein todne ki zimmedar hai. Isme MoviePy use hota hai audio nikalne ke liye aur Pydub use hota hai us audio ko 10-10 minute ke hisson mein batne ke liye (kyun ke Whisper API ki limit hoti hai). Ek non-obvious behavior ye hai ke file memory leak se bachne ke liye video clip ko explicitly close kiya jata hai.

**app/services/evaluation_service.py**
Ye file generated quiz ki quality check karti hai LLM ko use karke (G-Eval approach). Ye transcript, summary, aur final quiz ko as input leti hai aur ek score (out of 10) aur feedback generate karti hai. Ye directly `ChatGroq` use karti hai aur `QuizEvaluation` Pydantic schema mein response return karti hai.

**app/services/pdf_service.py**
Is file ka kaam uploaded PDF document ko parhna aur usme se raw text extract karna hai. Ye `pdfplumber` library use karti hai har page ko traverse karke text nikalne ke liye. Agar PDF mein sirf images hon (scanned PDF), to ye error throw karti hai kyun ke isme OCR nahi hai, yehi baat naye developer ko yaad rakhni chahiye.

**app/services/quiz_service.py**
Ye service summary aur transcript input le kar multiple choice questions (MCQs) generate karti hai. Ye Groq LLM ko `with_structured_output` aur `json_mode` ke sath call karti hai taake response hamesha strict JSON format mein aaye. Ye file transcript ko 4000 characters tak truncate kar deti hai taake token limit exceed na ho.

**app/services/summary_service.py**
Ye service bohot lambe video transcript ya PDF text ko ek concise educational summary mein convert karti hai. Isme bhi ChatGroq LLM ka istemal hota hai jisko `SUMMARY_PROMPT` pass kiya jata hai. Ye text generate karke quiz pipeline ko forward karti hai.

**app/services/upload_service.py**
Ye file users ki upload ki gayi videos ko system mein securely save karne ka logic handle karti hai. Ye file extensions (.mp4, .mkv) aur MIME types ko validate karti hai. Agar file size theek ho to ye usay ek UUID de kar `uploads` folder mein likh deti hai.

**app/services/web_search_service.py**
Ye service kisi topic par quiz banane ke liye internet se information lane ka kaam karti hai. Ye `duckduckgo-search` library use karti hai aur results nikal kar unke text ko ek jagah combine kar ke return karti hai. Ye transcript ki jagah input ka kaam karta hai jab user ke paas koi file na ho.

**app/services/whisper_service.py**
Ye file audio chunks ko text (transcription) mein convert karti hai. Ye Groq ki Whisper API (OpenAI compatible endpoint) ko audio file bhejti hai aur return mein transcript text leti hai. Phir ye saare chunks ke transcripts ko jor (concatenate) kar ek final text bana deti hai.

**app/utils/auth.py**
Is file mein security ke saare main utilities maujood hain, jaise password hashing aur JWT tokens banana. Ye ek `@require_auth` decorator bhi define karti hai jo kisi bhi API route par lagaya ja sakta hai taake sirf logged-in users usay access kar sakein. Ye file Flask ke `g` object mein current user ki ID set karti hai taake routes usay baad mein read kar sakein.

**app/utils/helpers.py**
Is file mein choti utilities hoti hain jo code ko saaf rakhti hain. Mainly isme `safe_delete_file` ka function hai jo disk se file ko delete karta hai aur agar file na mile ya permission na ho to quietly error log kar deta hai crash karne ke bajaye. Ye `routes.py` mein pipeline complete hone ke baad temp files clean karne ke liye use hota hai.

**app/utils/logger.py**
Ye file application-wide standard logging setup karti hai. Isme console output aur file output donon define hote hain taake bugs easily track ho sakein. Ye `logging` module ka ek pre-configured instance return karti hai jisko har service `get_logger()` call karke use karti hai.

**app/utils/openai_error_handler.py**
Ye decorator aur helper class hai jo API limits aur timeouts ko gracefully catch karta hai. Agar LLM provider ka server down ho ya rate limit aye, to ye normal Python exceptions ko `OpenAIServiceError` mein map kar deta hai. Is se front-end ko user-friendly error messages aur correct HTTP status codes bhejna aasan ho jata hai.

**app/utils/validators.py**
Ye file text inputs jaise email formatting aur password strength ko check karne ke functions rakhti hai. Ye ensure karti hai ke password mein number, special character aur sahi length maujood ho. Ye mainly `auth_routes.py` mein signup/change password ke waqt use hoti hai.

**frontend/app.py**
Ye chota Flask server hai jo sirf frontend ki static HTML, CSS, aur JS files serve karta hai. Ye SPA (Single Page App) routes ko handle karne ke liye sab paths par `index.html` fallback deta hai (catch-all route). Ye environment variables se backend URL read karke client ko `/config` route par pass bhi karta hai.

**frontend/auth_utils.py**
Ye file Streamlit UI ke liye authentication helpers rakhti hai, yani jab Streamlit frontend use hota hai to API calls ke liye headers banana aur token refresh karna iska kaam hai. Isme `requests` library ka use karke backend se session manage kiya jata hai.

## 4. END-TO-END REQUEST FLOWS

**a. User signup karta hai**
1. User frontend se username, email, aur password bhejta hai `POST /auth/signup` (auth_routes.py).
2. Backend input validate karta hai (validators.py, `is_valid_email`, password strength).
3. Database mein check hota hai ke email/username already exist to nahi karte (User model query).
4. `hash_password` (utils/auth.py) use kar ke password encrypt hota hai aur `User` object `db.session.add` se DB mein insert hota hai.
5. `generate_access_token` aur `generate_refresh_token` (utils/auth.py) call hote hain.
6. Refresh token ka hash ban kar `RefreshToken` table mein save hota hai.
7. Success response (tokens + user info) HTTP 201 ke sath frontend ko return hota hai.

**b. User login karta hai**
1. User frontend se email/username aur password bhejta hai `POST /auth/login` (auth_routes.py).
2. (Rate limit check hota hai flask-limiter se).
3. Backend DB se user dhoondta hai `User.query.filter`.
4. `verify_password` (utils/auth.py) call karke provided password ko DB hash se match karta hai.
5. Agar sahi ho to, naye JWT tokens generate hote hain aur naya refresh token hash DB mein save hota hai.
6. Success response frontend ko return hota hai.

**c. User video se quiz generate karta hai**
1. **Upload:** User frontend se `POST /upload-video` (routes.py) par file bhejta hai. `UploadService.handle_upload` video ko validate karke `uploads` folder mein UUID ke naam se save karti hai aur `video_id` return karti hai.
2. **Trigger:** User `POST /generate-quiz` (routes.py) par `video_id` bhejta hai.
3. **Audio Extraction:** `AudioService.extract_audio` MoviePy use karke us video se WAV audio track extract karke temp folder mein save karta hai.
4. **Chunking:** `AudioService.chunk_audio` Pydub use karke us WAV audio ko 10-minute ke MP3 chunks mein split karta hai.
5. **Transcription:** `WhisperService.transcribe_chunks` un chunks ko Groq API ko bhejta hai aur poori video ka ek text transcript banata hai.
6. **Summarization:** `SummaryService.generate_summary` us transcript ko LLM ke paas bhej kar concise educational summary lata hai.
7. **Quiz Generation:** `QuizService.generate_quiz` summary aur transcript le kar Groq LLM se JSON mode mein MCQs generate karwata hai (`QuizResponse` schema use kar ke).
8. **Evaluation:** `EvaluationService.evaluate_quiz` banaye gaye quiz ko check karke G-Eval score (e.g. 8.5/10) aur feedback lata hai.
9. **Database Save:** `_persist_quiz_to_db` helper method pehle `VideoJob` ka record banata hai, phir `QuizResult` ka record banata hai (linking them) aur PostgreSQL mein save kar deta hai.
10. **File Cleanup:** Temp files (`video`, `wav`, `mp3 chunks`) `safe_delete_file` ke zariye system se delete ki jati hain.
11. Final JSON format response user ko return hota hai aur outputs folder mein JSON backup save hota hai.

**d. User PDF se quiz generate karta hai**
1. User multipart form data mein PDF bhejta hai `POST /generate-quiz-from-pdf` (routes.py) par.
2. Endpoint file ko temporarily save karta hai.
3. `PDFService.extract_text` pdfplumber use karke saare pages se raw text nikalta hai. (Audio/Whisper steps skip hote hain).
4. Us text ko lekar seedha `SummaryService.generate_summary` call hota hai.
5. Phir `QuizService.generate_quiz` text se quiz banata hai.
6. `EvaluationService.evaluate_quiz` se score aata hai.
7. `_persist_quiz_to_db` mein `VideoJob` (source_type="pdf") aur `QuizResult` save hote hain.
8. Temp PDF file delete ki jati hai aur frontend ko response bhej diya jata hai.

**e. User topic se quiz generate karta hai**
1. User `POST /generate-quiz-from-topic` (routes.py) par topic string bhejta hai.
2. `WebSearchService.search_topic` DuckDuckGo API use kar ke topic par web results search karta hai aur content extract kar k combine text banata hai.
3. Ye web text seedha `SummaryService.generate_summary` ko pass hota hai.
4. Phir `QuizService.generate_quiz` us summary aur web text se questions banata hai.
5. `EvaluationService.evaluate_quiz` score lagata hai.
6. `_persist_quiz_to_db` mein `VideoJob` (source_type="topic") aur `QuizResult` create hote hain.
7. Response frontend ko return ho jata hai.

**f. User "My Quizzes" dekhta hai**
1. User frontend se `GET /quizzes` (routes.py) hit karta hai.
2. `@require_auth` se token verify hota hai aur `g.current_user.id` nikalta hai.
3. Backend `QuizResult` table mein query karta hai, usay `VideoJob` ke sath join karta hai `outerjoin(VideoJob)`, aur user ki id par filter laga kar descend order (date) mein list fetch karta hai.
4. List (id, title, score, source_type) JSON ban kar return hoti hai.

**g. Expired access token use hota hai**
1. Frontend kisi route par API request marta hai (e.g. `/quizzes`) expired token k sath.
2. `@require_auth` (auth.py) JWT verify karta hai aur `jwt.ExpiredSignatureError` catch karke `401 Unauthorized` bhejta hai "Token has expired" message k sath.
3. Frontend (app.js) 401 response dekhta hai.
4. Frontend silently `/auth/refresh` par POST request bhejta hai apna `refresh_token` de kar.
5. `auth_routes.py` ka `/refresh` endpoint refresh token verify karta hai, database check karta hai ke revoked to nahi.
6. Phir new access token aur new refresh token bana kar bhejta hai aur purane wale ko `revoked=True` mark kar deta hai.
7. Frontend naye tokens save karta hai aur apni pichli request (`/quizzes`) naye token k sath retry karta hai.

## 5. DATABASE SCHEMA

Yahan exact SQLAlchemy models ka structure bayan kiya gaya hai:

**users table:**
- `id`: UUID (Primary Key) - User ki unique pehchan.
- `username`: String(150) (Unique, Indexed, Nullable=False) - Login username.
- `email`: String(255) (Unique, Indexed, Nullable=False) - Login email.
- `password_hash`: String(255) (Nullable=False) - Encrypted password.
- `is_active`: Boolean (Default=True) - Account enable/disable status.
- `is_verified`: Boolean (Default=True) - Email verified hai ya nahi.
- `created_at`: DateTime - Record kab bana.
- `updated_at`: DateTime - Record kab last change hua.
*Relationships:* `video_jobs`, `quiz_results`, `refresh_tokens` tables ke sath 1-to-Many relation.

**refresh_tokens table:**
- `id`: UUID (Primary Key).
- `user_id`: UUID (Foreign Key -> users.id, Cascade Delete).
- `token_hash`: String(255) (Nullable=False) - SHA256 hashed refresh token.
- `expires_at`: DateTime (Nullable=False) - Token expiry date.
- `revoked`: Boolean (Default=False) - Token manually expire kar dia gaya hai ya nahi.
- `created_at`: DateTime.
*Relationships:* Back-populates `user`.

**video_jobs table:**
- `id`: UUID (Primary Key).
- `user_id`: UUID (Foreign Key -> users.id, Cascade Delete).
- `original_filename`: String(255) (Nullable=False) - Uploaded file ka asal naam.
- `stored_path`: String(500) (Nullable=True) - Disk par kahan save hui (pdf/video k case mein).
- `source_type`: String(50) (Nullable=False) - Ye batata hai input kya tha ("video", "pdf", ya "topic").
- `created_at`: DateTime.
*Relationships:* Back-populates `user`, aur `quiz_results` (1-to-Many).

**quiz_results table:**
- `id`: UUID (Primary Key).
- `user_id`: UUID (Foreign Key -> users.id, Cascade Delete).
- `video_job_id`: UUID (Foreign Key -> video_jobs.id, Set Null).
- `title`: String(255) (Nullable=False) - Quiz ka title.
- `summary`: Text (Nullable=True) - Video/Text ki summary.
- `quiz_json`: JSON (Nullable=False) - Array of multiple choice questions, options, answers.
- `evaluation_score`: Float (Nullable=True) - G-Eval ki rating (0 se 10).
- `evaluation_feedback`: Text (Nullable=True) - LLM ka reason score dene ka.
- `transcript`: Text (Nullable=True) - Source video ka audio text ya PDF ka extract kiya gaya text.
- `created_at`: DateTime.
*Relationships:* Back-populates `user` aur `video_job`.

## 6. CONFIGURATION
Ye project `.env` file aur environment variables se ye parameters read karta hai (`app/config/settings.py` ke zariye):

- `FLASK_ENV`: (Default 'development') Control karta hai ke app dev mode mein hai ya production mein. Production mein database validations strict hoti hain.
- `PORT` / `HOST`: Flask app kis port (e.g. 5000) aur IP par listen karegi.
- `GROQ_API_KEY`: Groq LLM service use karne ki API key. Iske bina app AI quiz nahi bana sakti.
- `GROQ_CHAT_MODEL`: (Default 'llama-3.1-8b-instant') Quiz generation aur summary ke liye LLM model ka naam.
- `GROQ_EVAL_MODEL`: Evaluation prompt k liye model ka naam.
- `GROQ_WHISPER_MODEL`: (Default 'whisper-large-v3') Audio ko text banane k liye model ka naam.
- `UPLOAD_FOLDER`, `TEMP_FOLDER`, `OUTPUT_FOLDER`, `LOG_FOLDER`: Directories ke paths jahan system files store/process karega.
- `MAX_UPLOAD_SIZE`: (Default 104857600 bytes yani 100MB) Maximum file size jo user upload kar sakta hai.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: Docker mein PostgreSQL database set karne k liye use hote hain.
- `DATABASE_URL`: SQLAlchemy ko is URL se database se connect kiya jata hai (jaise `postgresql://quizapp:quizpass@db:5432/ai_quiz_generator`).
- `JWT_SECRET_KEY`: Ek long random string jo JWT tokens ko encrypt aur sign karne k liye use hoti hai. Ye lazmi set karni hoti hai.
- `JWT_ACCESS_EXPIRY_MINUTES`: Access token ki life time (e.g. 60 minutes).
- `JWT_REFRESH_EXPIRY_DAYS`: Refresh token ki life time (e.g. 30 days).
- `ALLOWED_ORIGINS`: CORS headers setup karta hai (e.g. `*` for all).
- `BACKEND_URL`: Frontend SPA ko batata hai ke API calls kis domain/port (backend server) par bhejni hain.

## 7. HOW TO RUN (as it actually works right now)

**Option 1: Local Development (bina Docker ke)**
1. **Prerequisites:** Aapke paas Python 3.12, PostgreSQL database, aur `ffmpeg` system par install aur PATH mein hone chahiye.
2. **Environment Variables:** Project folder mein `.env.example` ko copy kar k `.env` banayen. Isme `GROQ_API_KEY`, `JWT_SECRET_KEY` set karein. `DATABASE_URL` ko update karein apnay local PostgreSQL server k mutabiq (jaise `postgresql://quizapp:quizpass@localhost:5432/ai_quiz_generator`).
3. **Dependencies Install:** Terminal mein `python -m venv venv`, phir usay activate karke `pip install -r requirements.txt` run karein.
4. **Database Migration:** Table schema bananay k liye `flask db upgrade` chalayen. (Agar migration folder nahi bana to pehle `flask db init` aur `flask db migrate -m "init"` karein, wese code mein lagta hai setup complete hai).
5. **Run Backend:** Terminal mein `python app.py` ya `flask run` execute karein. Backend `http://127.0.0.1:5000` par chal jayega.
6. **Run Frontend:** Ek aur terminal open karein aur `python frontend/app.py` execute karein. Ye `http://127.0.0.1:8501` par frontend serve karega. Browser mein ye address open karein.

**Option 2: Docker / Docker Compose ke zariye**
1. **Environment Variables:** Project folder mein `.env.example` ko copy karke `.env` banayein aur usme `GROQ_API_KEY` aur `JWT_SECRET_KEY` daalein. (Yahan `DATABASE_URL` ko as-is rehne dein kyun k wo Docker service `db` k liye configured hai).
2. **Build aur Start:** Terminal mein `docker-compose up --build -d` chalayen. Ye backend, frontend aur postgres database k containers download aur run kardega.
3. **Database Migration in Docker:** First time tables bananay k liye container ke andar migration chalani hogi: `docker-compose exec backend flask db upgrade` (ya agar entrypoint.sh mein auto-migration likhi hui hai to wo khud tables bana lega, wese manual chalana safe hai).
4. **Access UI:** Browser kholein aur `http://localhost:8501` par ja kar application use karein. API backend `http://localhost:5000` par run horaha hoga.

## 8. KNOWN GAPS / TODOs
- **Streamlit Frontend Mismatch:** `requirements.txt` aur `docker-compose.yml` mein `streamlit` framework mention hai aur `frontend/auth_utils.py` bhi likha hua hai, lekin `frontend/static` folder mein ek Vanilla JS/HTML ki Single Page Application (SPA) bani hui hai jo `frontend/app.py` host kar raha hai. Ye do alag UI approaches codebase mein mix ho gaye hain (SPA vs Streamlit).
- **Entrypoint Script Visibility:** `Dockerfile.backend` file `deploy/entrypoint.sh` run karti hai jo default migration logic rakhta hai lekin iski robust error handling ya timeout delays pata nahi hain jo startup issues create kar sakti hai.
- **Outdated Plan Artifacts:** Project root par `project_audit.md` mojood hai jo shayad purane architecture ka hissa hai. Ye documentation actual current codebase se alag ho sakti hai.
- **Audio Extraction Limitation:** `AudioService` mein `ffmpeg` parameters hardcode hain. Agar kisi video format mein ajeeb codecs hue to conversion fail ho sakti hai. Pydub memory mein puri file load karta hai jo bohot large videos par system memory exhaust (OOM) kar sakta hai.
- **Error Types in PDF Service:** `PDFService` mein directly raw text extract hota hai. Agar koi heavily formatted PDF ya non-standard characters wala document ho to usko process karne ki edge cases poori tarah clear handle nahi ho rahin.
