# Implementation Plan: Quiz Difficulty Level Selection & Quiz Timer Option

## Key Discovery

**quiz_prompt.py already has `{difficulty_level}` in the PromptTemplate** with full Beginner/Intermediate/Advanced guidance text (lines 15-24). The `QUIZ_PROMPT` input_variables already include `"difficulty_level"`. The only problem is that `QuizService.generate_quiz()` doesn't pass `difficulty_level` when invoking the chain — it only passes `summary` and `transcription` (line 61-63). This means the prompt receives an empty string for `{difficulty_level}`.

Similarly, `_persist_quiz_to_db()` doesn't accept or store `difficulty` or `time_limit_minutes`.

---

## Files to Create (1)

### 1. `migrations/versions/a1b2c3d4e5f6_add_difficulty_and_time_limit_to_quiz_results.py`
**NEW FILE** — Alembic migration adding `difficulty` (String, default "Intermediate") and `time_limit_minutes` (Integer, nullable) columns to `quiz_results`. Follows the exact pattern of existing migrations.

---

## Files to Modify (6)

### 1. `app/services/quiz_service.py` — 2 small additions
- **Line 35**: Add optional `difficulty: str = "Intermediate"` parameter to `generate_quiz()` signature
- **Lines 50-52**: Add validation that `difficulty` is one of the 3 allowed values, defaulting to "Intermediate" on invalid/empty input
- **Line 61**: Pass `difficulty_level` (the prompt variable name) to the chain invoke alongside `summary` and `transcription`

### 2. `app/api/routes.py` — 4 small additions (one per endpoint + 2 helper updates)

**Helper `_persist_quiz_to_db()`:**
- Add optional parameters `difficulty: str = "Intermediate"` and `time_limit_minutes: Optional[int] = None`
- Pass them to the `QuizResult()` constructor (lines 138-147)

**Helper `_build_quiz_response()`:**
- Add optional parameters `difficulty: str = "Intermediate"` and `time_limit_minutes: Optional[int] = None`
- Include them in the returned dict as new top-level keys

**Endpoint `/generate-quiz` (line 208):**
- Parse optional `difficulty` from `data.get("difficulty", "Intermediate")`
- Parse optional `time_limit_minutes` from `data.get("time_limit_minutes")`
- Pass both to `QuizService.generate_quiz(..., difficulty=difficulty)`
- Pass both to `_build_quiz_response(..., difficulty=difficulty, time_limit_minutes=time_limit_minutes)`
- Pass both to `_persist_quiz_to_db(..., difficulty=difficulty, time_limit_minutes=time_limit_minutes)`

**Endpoint `/generate-quiz-from-pdf` (line 384):**
- Parse optional `difficulty` from `request.form.get("difficulty", "Intermediate")` (multipart form)
- Parse optional `time_limit_minutes` from `request.form.get("time_limit_minutes")` (multipart form)
- Wire through same as above

**Endpoint `/generate-quiz-from-topic` (line 535):**
- Parse optional `difficulty` from `data.get("difficulty", "Intermediate")` (JSON body)
- Parse optional `time_limit_minutes` from `data.get("time_limit_minutes")` (JSON body)
- Wire through same as above

**Endpoint `/generate-quiz-from-youtube` (line 662):**
- Parse optional `difficulty` from `data.get("difficulty", "Intermediate")` (JSON body)
- Parse optional `time_limit_minutes` from `data.get("time_limit_minutes")` (JSON body)
- Wire through same as above

**Endpoint `GET /quiz/<id>` (line 874):**
- Include `difficulty` and `time_limit_minutes` in the quiz retrieval response (read from DB model)

**Endpoint `GET /download/<id>` (line 979):**
- Include `difficulty` and `time_limit_minutes` in the downloaded JSON

### 3. `app/models/quiz_result.py` — 2 new columns
- Add `difficulty = db.Column(db.String(50), nullable=True, default="Intermediate")`
- Add `time_limit_minutes = db.Column(db.Integer, nullable=True, default=None)`

### 4. `frontend/static/index.html` — 4 small additions (one per quiz generation view)

Each of the 4 quiz generation views gets a "Quiz Options" section before the generate button containing:
- Difficulty dropdown: Beginner / Intermediate (default) / Advanced
- Time Limit control: Unlimited (default) / Timed (reveals minutes input)

**Video view (`view-video`, line 410):** Insert before `btn-generate-video-quiz` button
**PDF view (`view-pdf`, line 458):** Insert before `btn-generate-pdf-quiz` button
**Topic view (`view-topic`, line 506):** Insert inside `topic-quiz-form` before the submit button
**YouTube view (`view-youtube`, line 547):** Insert inside `youtube-quiz-form` before the submit button

**Quiz player view (`view-quiz`, line 601):** Add a timer display element between the title and tabs

### 5. `frontend/static/app.js` — Targeted additions

**New global variables (near line 5):**
- `let quizTimerInterval = null;`
- `let quizTimeRemaining = 0;`

**New function `getQuizOptions(pageId)`** — Reads difficulty and time_limit_minutes from the DOM elements for a given page

**Modified `handleGenerateVideoQuiz()`** — Read quiz options, include difficulty and time_limit_minutes in the JSON body to `/generate-quiz`

**Modified `handleGeneratePdfQuiz()`** — Read quiz options, append to FormData

**Modified `handleGenerateTopicQuiz()`** — Read quiz options, include in JSON body

**Modified `handleGenerateYoutubeQuiz()`** — Read quiz options, include in JSON body

**Modified `loadQuizIntoPlayer()`** — Store `time_limit_minutes` and `difficulty` from response; if time_limit > 0, call `startQuizTimer()`

**New function `startQuizTimer(durationMinutes, onExpire)`** — Self-contained countdown timer
- Shows timer bar/countdown in quiz view header
- Counts down every second
- On expiry, calls `handleQuizSubmission` programmatically, shows time-expired message

**Modified `handleQuizSubmission()`** — Clear timer interval if active

**Modified `handleQuizRetake()`** — Clear any existing timer, restart if time_limit is set

**Modified `switchView()` / `switchQuizTab()`** — Ensure timer display is properly managed

**New CSS** — Timer styling (countdown bar, pulsing when low time)

### 6. `frontend/static/style.css` — Minor addition
- Timer bar/countdown styling classes

---

## Detailed Change Specifications

### quiz_service.py changes

```python
# Line 35 — change signature:
def generate_quiz(self, summary: str, transcription: str, difficulty: str = "Intermediate") -> QuizResponse:

# After line 49 (before truncation) — add validation:
valid_difficulties = {"Beginner", "Intermediate", "Advanced"}
if not difficulty or difficulty.strip() not in valid_difficulties:
    difficulty = "Intermediate"
difficulty = difficulty.strip()

# Line 61 — add difficulty_level to invoke:
quiz_response: QuizResponse = self.chain.invoke({
    "summary": summary,
    "transcription": transcription_excerpt,
    "difficulty_level": difficulty,
})
```

### routes.py — _persist_quiz_to_db changes

```python
# Signature — add 2 params:
def _persist_quiz_to_db(
    user_id, original_filename, stored_path, source_type,
    title, summary, quiz_json, evaluation_score,
    evaluation_feedback, transcript,
    difficulty="Intermediate", time_limit_minutes=None,
) -> Optional[str]:

# QuizResult constructor — add 2 fields:
quiz_result = QuizResult(
    ...existing fields...,
    difficulty=difficulty,
    time_limit_minutes=time_limit_minutes,
)
```

### routes.py — _build_quiz_response changes

```python
def _build_quiz_response(quiz_result, summary, evaluation_result,
                         difficulty="Intermediate", time_limit_minutes=None):
    ...
    return {
        ...existing fields...,
        "difficulty": difficulty,
        "time_limit_minutes": time_limit_minutes,
    }
```

### routes.py — Per-endpoint changes

Each of the 4 endpoints needs to:
1. Extract difficulty from request (JSON or form data)
2. Extract time_limit_minutes from request
3. Validate difficulty (clamp to valid set, default "Intermediate")
4. Validate time_limit_minutes (must be positive int if provided, else None)
5. Pass both to generate_quiz(), _build_quiz_response(), and _persist_quiz_to_db()

### Frontend UI pattern for quiz options

The new controls use existing Tailwind classes from the design system. Pattern for each generation page:

```html
<!-- Quiz Options (new section) -->
<div class="glass-card rounded-xl p-4 border border-white/5 space-y-4">
    <p class="text-xs font-bold uppercase tracking-wider text-on-surface-variant/70">Quiz Options</p>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
            <label class="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/60 mb-1.5">Difficulty</label>
            <select id="{page}-difficulty" class="w-full bg-surface-container-low/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-on-surface">
                <option value="Beginner">Beginner</option>
                <option value="Intermediate" selected>Intermediate</option>
                <option value="Advanced">Advanced</option>
            </select>
        </div>
        <div>
            <label class="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/60 mb-1.5">Time Limit</label>
            <select id="{page}-time-limit" class="w-full bg-surface-container-low/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-on-surface" onchange="toggleTimeInput('{page}')">
                <option value="0" selected>Unlimited</option>
                <option value="custom">Timed</option>
            </select>
        </div>
    </div>
    <div id="{page}-time-input-group" class="hidden">
        <label class="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/60 mb-1.5">Duration (minutes)</label>
        <input type="number" id="{page}-time-minutes" min="1" max="120" value="10" class="w-full bg-surface-container-low/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-on-surface">
    </div>
</div>
```

### Timer in Quiz Player

The timer appears in the quiz player view header area (between title and tabs):

```html
<!-- Timer bar (hidden by default, shown when timed quiz is active) -->
<div id="quiz-timer-bar" class="hidden glass-card rounded-xl p-4 border border-primary/20 flex items-center justify-between">
    <div class="flex items-center gap-2">
        <span class="material-symbols-outlined text-primary text-lg">timer</span>
        <span class="text-xs font-bold text-on-surface-variant/70 uppercase tracking-wider">Time Remaining</span>
    </div>
    <span id="quiz-timer-display" class="text-lg font-extrabold text-primary font-mono">--:--</span>
</div>
```

### Timer JavaScript

```javascript
let quizTimerInterval = null;
let quizTimeRemaining = 0;

function startQuizTimer(durationMinutes, onExpire) {
    clearQuizTimer();
    quizTimeRemaining = durationMinutes * 60;
    const timerBar = document.getElementById("quiz-timer-bar");
    const timerDisplay = document.getElementById("quiz-timer-display");
    timerBar.classList.remove("hidden");
    
    function updateDisplay() {
        const mins = Math.floor(quizTimeRemaining / 60);
        const secs = quizTimeRemaining % 60;
        timerDisplay.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
        
        // Urgency styling when < 60s remaining
        if (quizTimeRemaining <= 60) {
            timerDisplay.classList.add("text-error");
            timerDisplay.classList.remove("text-primary");
        }
    }
    
    updateDisplay();
    quizTimerInterval = setInterval(() => {
        quizTimeRemaining--;
        updateDisplay();
        if (quizTimeRemaining <= 0) {
            clearQuizTimer();
            showToast("Time Expired", "Your quiz has been auto-submitted.", true);
            onExpire();
        }
    }, 1000);
}

function clearQuizTimer() {
    if (quizTimerInterval) {
        clearInterval(quizTimerInterval);
        quizTimerInterval = null;
    }
    const timerBar = document.getElementById("quiz-timer-bar");
    const timerDisplay = document.getElementById("quiz-timer-display");
    if (timerBar) timerBar.classList.add("hidden");
    if (timerDisplay) {
        timerDisplay.classList.remove("text-error");
        timerDisplay.classList.add("text-primary");
    }
}
```

---

## Backward Compatibility Analysis

- **No new required fields**: Both `difficulty` and `time_limit_minutes` are optional everywhere. Old frontend code that doesn't send them gets safe defaults (Intermediate, unlimited).
- **DB migration safe**: Both columns are nullable or have server defaults. Existing rows unaffected.
- **Prompt unchanged for Intermediate**: The existing prompt text already handles `{difficulty_level}` — when "Intermediate" is passed, the behavior matches the existing implicit behavior (the empty-string behavior was slightly different but "Intermediate" is explicitly described as the baseline).
- **Timer client-side only**: No server-side timer enforcement. Old quizzes without timer data show no timer.
- **Response shape additive only**: New fields `difficulty` and `time_limit_minutes` added to response JSON. No existing fields removed or renamed.
