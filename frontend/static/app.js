let BACKEND_URL = "http://127.0.0.1:5000";
let currentUser = null;
let currentQuiz = null;
let userAnswers = {};
let activeQuizTab = "take";

// Initialize App
document.addEventListener("DOMContentLoaded", async () => {
    await fetchConfig();
    setupEventListeners();
    checkAuthSession();
});

// Fetch configuration from the frontend server
async function fetchConfig() {
    try {
        const response = await fetch("/config");
        if (response.ok) {
            const data = await response.json();
            if (data.BACKEND_URL) {
                BACKEND_URL = data.BACKEND_URL.replace(/\/$/, "");
            }
        }
    } catch (e) {
        console.warn("Could not load backend config, using default:", BACKEND_URL);
    }
}

// Setup all Event Listeners
function setupEventListeners() {
    // Auth Tabs
    document.getElementById("tab-login-btn").addEventListener("click", () => toggleAuthTab("login"));
    document.getElementById("tab-signup-btn").addEventListener("click", () => toggleAuthTab("signup"));

    // Forms
    document.getElementById("login-form").addEventListener("submit", handleLogin);
    document.getElementById("signup-form").addEventListener("submit", handleSignup);

    // Sidebar navigation
    document.querySelectorAll("#sidebar-nav button").forEach(btn => {
        btn.addEventListener("click", () => {
            const page = btn.getAttribute("data-page");
            switchView(page);
        });
    });

    // Quick create quiz
    document.getElementById("quick-create-btn").addEventListener("click", () => {
        switchView("topic");
    });

    // Logout
    document.getElementById("logout-btn").addEventListener("click", handleLogout);

    // Video upload drag-and-drop
    setupDragAndDrop("video");

    // PDF upload drag-and-drop
    setupDragAndDrop("pdf");

    // Topic quiz form
    document.getElementById("topic-quiz-form").addEventListener("submit", handleGenerateTopicQuiz);

    // Active Quiz Tabs
    document.getElementById("quiz-tab-take").addEventListener("click", () => switchQuizTab("take"));
    document.getElementById("quiz-tab-summary").addEventListener("click", () => switchQuizTab("summary"));
    document.getElementById("quiz-tab-eval").addEventListener("click", () => switchQuizTab("eval"));

    // Quiz form submit
    document.getElementById("active-quiz-form").addEventListener("submit", handleQuizSubmission);
    document.getElementById("btn-retake-quiz").addEventListener("click", handleQuizRetake);

    // Download Quiz JSON
    document.getElementById("btn-download-json").addEventListener("click", downloadQuizJSON);
}

// Check if user session exists in localStorage
async function checkAuthSession() {
    const accessToken = localStorage.getItem("accessToken");
    if (accessToken) {
        // Test auth by fetching profile
        const success = await loadUserProfile();
        if (success) {
            hideAuthShowApp();
            checkBackendHealth();
            loadDashboardStats();
        } else {
            clearSession();
        }
    } else {
        clearSession();
    }
}

// Hide auth screen and show main system shell
function hideAuthShowApp() {
    document.getElementById("auth-container").classList.add("hidden");
    document.getElementById("app-shell").classList.remove("hidden");
    switchView("home");
}

// Show auth screen and hide main system shell
function showAuthHideApp() {
    document.getElementById("auth-container").classList.remove("hidden");
    document.getElementById("app-shell").classList.add("hidden");
    toggleAuthTab("login");
}

function clearSession() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    currentUser = null;
    currentQuiz = null;
    userAnswers = {};
    showAuthHideApp();
}

// Toggle between Login and Signup tabs
function toggleAuthTab(tab) {
    const loginBtn = document.getElementById("tab-login-btn");
    const signupBtn = document.getElementById("tab-signup-btn");
    const loginForm = document.getElementById("login-form");
    const signupForm = document.getElementById("signup-form");

    if (tab === "login") {
        loginBtn.className = "flex-1 pb-3 text-center border-b-2 border-primary font-bold text-primary transition-all duration-300";
        signupBtn.className = "flex-1 pb-3 text-center border-b-2 border-transparent text-on-surface-variant hover:text-on-surface transition-all duration-300";
        loginForm.classList.remove("hidden");
        signupForm.classList.add("hidden");
    } else {
        signupBtn.className = "flex-1 pb-3 text-center border-b-2 border-primary font-bold text-primary transition-all duration-300";
        loginBtn.className = "flex-1 pb-3 text-center border-b-2 border-transparent text-on-surface-variant hover:text-on-surface transition-all duration-300";
        signupForm.classList.remove("hidden");
        loginForm.classList.add("hidden");
    }
}

// Notification Toast Helpers
function showToast(title, message, isError = false) {
    const toast = document.getElementById("toast");
    const toastTitle = document.getElementById("toast-title");
    const toastMessage = document.getElementById("toast-message");
    const toastIcon = document.getElementById("toast-icon");

    toastTitle.textContent = title;
    toastMessage.textContent = message;

    if (isError) {
        toastIcon.textContent = "error";
        toastIcon.className = "material-symbols-outlined text-error";
        toast.classList.add("border-error/20");
        toast.classList.remove("border-white/10");
    } else {
        toastIcon.textContent = "info";
        toastIcon.className = "material-symbols-outlined text-primary";
        toast.classList.add("border-white/10");
        toast.classList.remove("border-error/20");
    }

    // Remove hidden/offscreen classes and add visible classes
    toast.classList.remove("translate-x-full", "opacity-0", "pointer-events-none");
    toast.classList.add("translate-x-0", "opacity-100");

    // Auto hide after 5 seconds
    if (window.toastTimeout) {
        clearTimeout(window.toastTimeout);
    }
    window.toastTimeout = setTimeout(hideToast, 5000);
}

function hideToast() {
    const toast = document.getElementById("toast");
    if (!toast) return;
    
    // Add hidden/offscreen classes and remove visible classes
    toast.classList.remove("translate-x-0", "opacity-100");
    toast.classList.add("translate-x-full", "opacity-0", "pointer-events-none");
}


// Wrapper for API calls with token refresh capability
async function apiCall(endpoint, options = {}) {
    let accessToken = localStorage.getItem("accessToken");

    // Construct headers
    if (!options.headers) {
        options.headers = {};
    }

    // Don't override multipart content-type boundary
    if (!(options.body instanceof FormData)) {
        options.headers["Content-Type"] = "application/json";
    }

    if (accessToken) {
        options.headers["Authorization"] = `Bearer ${accessToken}`;
    }

    let url = endpoint.startsWith("http") ? endpoint : `${BACKEND_URL}${endpoint}`;
    let response = await fetch(url, options);

    // Handle token refresh on 401
    if (response.status === 401 && localStorage.getItem("refreshToken")) {
        console.log("Access token expired, attempting token refresh...");
        const refreshSuccess = await refreshAccessToken();
        if (refreshSuccess) {
            // Retry request with new token
            accessToken = localStorage.getItem("accessToken");
            options.headers["Authorization"] = `Bearer ${accessToken}`;
            response = await fetch(url, options);
        } else {
            clearSession();
            showToast("Session Expired", "Please log in again.", true);
            throw new Error("Session expired");
        }
    }

    return response;
}

// Call /auth/refresh to rotate tokens
async function refreshAccessToken() {
    const refreshToken = localStorage.getItem("refreshToken");
    if (!refreshToken) return false;

    try {
        const response = await fetch(`${BACKEND_URL}/auth/refresh`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem("accessToken", data.access_token);
            localStorage.setItem("refreshToken", data.refresh_token);
            return true;
        }
    } catch (e) {
        console.error("Token refresh failed:", e);
    }
    return false;
}

// Fetch Profile data
async function loadUserProfile() {
    try {
        const response = await apiCall("/auth/me");
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            document.getElementById("user-display-name").textContent = currentUser.username;
            return true;
        }
    } catch (e) {
        console.error("Load user profile failed:", e);
    }
    return false;
}

// Login Submit Handler
async function handleLogin(e) {
    e.preventDefault();
    const usernameOrEmail = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;

    try {
        const response = await fetch(`${BACKEND_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username_or_email: usernameOrEmail, password: password })
        });

        const data = await response.json();
        if (response.ok) {
            localStorage.setItem("accessToken", data.access_token);
            localStorage.setItem("refreshToken", data.refresh_token);
            showToast("Login Successful", `Welcome back, ${data.user.username}!`);
            
            // Set user profile
            currentUser = data.user;
            document.getElementById("user-display-name").textContent = currentUser.username;

            hideAuthShowApp();
            checkBackendHealth();
            loadDashboardStats();
        } else {
            showToast("Login Failed", data.error || "Invalid username or password.", true);
        }
    } catch (err) {
        console.error(err);
        showToast("Connection Error", "Could not connect to the backend server.", true);
    }
}

// Signup Submit Handler
async function handleSignup(e) {
    e.preventDefault();
    const username = document.getElementById("signup-username").value.trim();
    const email = document.getElementById("signup-email").value.trim();
    const password = document.getElementById("signup-password").value;
    const confirmPassword = document.getElementById("signup-confirm-password").value;

    if (password !== confirmPassword) {
        showToast("Validation Error", "Passwords do not match.", true);
        return;
    }

    try {
        const response = await fetch(`${BACKEND_URL}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();
        if (response.ok) {
            localStorage.setItem("accessToken", data.access_token);
            localStorage.setItem("refreshToken", data.refresh_token);
            showToast("Registration Successful", "Your account has been created!");
            
            currentUser = data.user;
            document.getElementById("user-display-name").textContent = currentUser.username;

            hideAuthShowApp();
            checkBackendHealth();
            loadDashboardStats();
        } else {
            showToast("Registration Failed", data.error || "Please verify your input fields.", true);
        }
    } catch (err) {
        console.error(err);
        showToast("Connection Error", "Could not connect to the backend server.", true);
    }
}

// Logout Request Handler
async function handleLogout() {
    const refreshToken = localStorage.getItem("refreshToken");
    try {
        await apiCall("/auth/logout", {
            method: "POST",
            body: JSON.stringify({ refresh_token: refreshToken })
        });
    } catch (e) {
        console.warn("Backend logout request encountered an error:", e);
    }
    clearSession();
    showToast("Logged Out", "You have been securely logged out.");
}

// Switch between dashboard sections
function switchView(pageId) {
    const sections = ["home", "video", "pdf", "topic", "library", "quiz"];
    sections.forEach(sec => {
        const el = document.getElementById(`view-${sec}`);
        if (el) {
            if (sec === pageId) {
                el.classList.remove("hidden");
            } else {
                el.classList.add("hidden");
            }
        }
    });

    // Update active nav button
    document.querySelectorAll("#sidebar-nav button").forEach(btn => {
        const page = btn.getAttribute("data-page");
        if (page === pageId) {
            btn.className = "w-full flex items-center gap-4 px-4 py-3 rounded-xl text-primary font-bold border-r-2 border-primary bg-primary/10 transition-all duration-300";
        } else {
            btn.className = "w-full flex items-center gap-4 px-4 py-3 rounded-xl text-on-surface-variant/70 font-medium hover:bg-white/5 hover:text-primary transition-all duration-300";
        }
    });

    // Update breadcrumb
    const pageTitles = {
        home: "Home",
        video: "Video to Quiz",
        pdf: "PDF to Quiz",
        topic: "Topic to Quiz",
        library: "My Quizzes",
        quiz: "Interactive Quiz Player"
    };

    document.getElementById("breadcrumb-current").textContent = pageTitles[pageId] || "Home";

    // View specific actions
    if (pageId === "library") {
        loadUserLibrary();
    } else if (pageId === "home") {
        loadDashboardStats();
    }
}

// Health check to backend
async function checkBackendHealth() {
    const indicator = document.getElementById("backend-indicator");
    const statusText = document.getElementById("backend-status-text");

    try {
        const response = await fetch(`${BACKEND_URL}/health`);
        if (response.ok) {
            const data = await response.json();
            indicator.className = "w-2.5 h-2.5 rounded-full bg-tertiary animate-pulse";
            statusText.textContent = "Backend: Connected";
            
            // Set uptime or DB status if provided
            if (data.status && data.uptime_seconds) {
                const hrs = Math.floor(data.uptime_seconds / 3600);
                const mins = Math.floor((data.uptime_seconds % 3600) / 60);
                document.getElementById("stat-uptime").textContent = `${hrs}h ${mins}m`;
            }
        } else {
            throw new Error("Status unhealthy");
        }
    } catch (e) {
        indicator.className = "w-2.5 h-2.5 rounded-full bg-error animate-pulse";
        statusText.textContent = "Backend: Disconnected";
        document.getElementById("stat-uptime").textContent = "Offline";
    }
}

// Load stats into Dashboard
async function loadDashboardStats() {
    try {
        const response = await apiCall("/quizzes");
        if (response.ok) {
            const data = await response.json();
            const quizzes = data.quizzes || [];
            
            document.getElementById("stat-total-quizzes").textContent = quizzes.length;
            
            if (quizzes.length > 0) {
                const totalScore = quizzes.reduce((sum, q) => sum + (q.evaluation_score || 0), 0);
                const avgScore = (totalScore / quizzes.length).toFixed(1);
                document.getElementById("stat-avg-score").textContent = avgScore;
            } else {
                document.getElementById("stat-avg-score").textContent = "0.0";
            }
        }
    } catch (e) {
        console.error("Uptake statistics failed:", e);
    }
}

// Drag & Drop Setup
function setupDragAndDrop(type) {
    const dropzone = document.getElementById(`${type}-dropzone`);
    const fileInput = document.getElementById(`${type}-file-input`);
    const uploadInfo = document.getElementById(`${type}-upload-info`);
    const filenameLabel = document.getElementById(`${type}-filename`);
    const filesizeLabel = document.getElementById(`${type}-filesize`);
    const btnCancel = document.getElementById(`btn-cancel-${type}`);
    const btnGenerate = document.getElementById(`btn-generate-${type}-quiz`);

    let selectedFile = null;

    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("drag-zone-active");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("drag-zone-active");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag-zone-active");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    btnCancel.addEventListener("click", (e) => {
        e.stopPropagation();
        resetUpload();
    });

    if (type === "video") {
        btnGenerate.addEventListener("click", () => handleGenerateVideoQuiz(selectedFile));
    } else {
        btnGenerate.addEventListener("click", () => handleGeneratePdfQuiz(selectedFile));
    }

    function handleFileSelection(file) {
        // Validate extensions
        if (type === "video") {
            const allowed = ["mp4", "mov", "avi", "mkv"];
            const ext = file.name.split(".").pop().toLowerCase();
            if (!allowed.includes(ext)) {
                showToast("File Rejected", "Invalid video format.", true);
                return;
            }
        } else if (type === "pdf") {
            const ext = file.name.split(".").pop().toLowerCase();
            if (ext !== "pdf") {
                showToast("File Rejected", "Only PDF files are accepted.", true);
                return;
            }
        }

        selectedFile = file;
        filenameLabel.textContent = file.name;
        filesizeLabel.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;

        dropzone.classList.add("hidden");
        uploadInfo.classList.remove("hidden");

        // Enable generate button
        btnGenerate.disabled = false;
        btnGenerate.className = "w-full py-3.5 rounded-xl bg-gradient-to-r from-primary-container to-secondary-container text-on-primary font-bold shadow-lg hover:brightness-110 transition-all active:scale-[0.98] flex items-center justify-center gap-2";
    }

    function resetUpload() {
        selectedFile = null;
        fileInput.value = "";
        dropzone.classList.remove("hidden");
        uploadInfo.classList.add("hidden");
        
        btnGenerate.disabled = true;
        btnGenerate.className = "w-full py-3.5 rounded-xl bg-white/5 text-on-surface-variant/40 font-bold border border-white/5 cursor-not-allowed transition-all flex items-center justify-center gap-2";

        // Hide progress
        const progContainer = document.getElementById(`${type}-progress-container`);
        if (progContainer) progContainer.classList.add("hidden");
    }
}

// Upload & Generate Quiz from Video
async function handleGenerateVideoQuiz(file) {
    const progressContainer = document.getElementById("video-progress-container");
    const progressText = document.getElementById("video-progress-text");
    const progressBar = document.getElementById("video-progress-bar");
    const progressPct = document.getElementById("video-progress-pct");
    const btnGenerate = document.getElementById("btn-generate-video-quiz");
    const btnCancel = document.getElementById("btn-cancel-video");

    progressContainer.classList.remove("hidden");
    btnGenerate.disabled = true;
    btnCancel.disabled = true;

    // Step 1: Upload Video
    progressText.textContent = "Uploading video track...";
    progressBar.style.width = "10%";
    progressPct.textContent = "10%";

    const formData = new FormData();
    formData.append("file", file);

    try {
        const uploadResponse = await apiCall("/upload-video", {
            method: "POST",
            body: formData
        });

        if (!uploadResponse.ok) {
            const data = await uploadResponse.json();
            throw new Error(data.error || "Video upload failed");
        }

        const uploadData = await uploadResponse.json();
        const videoId = uploadData.video_id;

        // Step 2: Generate Quiz
        progressText.textContent = "Transcribing audio (Whisper) & creating quiz...";
        progressBar.style.width = "50%";
        progressPct.textContent = "50%";

        const genResponse = await apiCall("/generate-quiz", {
            method: "POST",
            body: JSON.stringify({ video_id: videoId })
        });

        progressBar.style.width = "100%";
        progressPct.textContent = "100%";

        const data = await genResponse.json();
        if (genResponse.ok) {
            showToast("Quiz Generated", "Successfully completed video-to-quiz pipeline!");
            loadQuizIntoPlayer(data);
        } else {
            throw new Error(data.error || "Generation pipeline failed");
        }
    } catch (e) {
        console.error(e);
        showToast("Pipeline Error", e.message || "An unexpected error occurred during processing.", true);
    } finally {
        btnCancel.disabled = false;
        // Trigger reset to default state
        document.getElementById("btn-cancel-video").click();
    }
}

// Upload & Generate Quiz from PDF
async function handleGeneratePdfQuiz(file) {
    const progressContainer = document.getElementById("pdf-progress-container");
    const progressText = document.getElementById("pdf-progress-text");
    const progressBar = document.getElementById("pdf-progress-bar");
    const progressPct = document.getElementById("pdf-progress-pct");
    const btnGenerate = document.getElementById("btn-generate-pdf-quiz");
    const btnCancel = document.getElementById("btn-cancel-pdf");

    progressContainer.classList.remove("hidden");
    btnGenerate.disabled = true;
    btnCancel.disabled = true;

    progressText.textContent = "Uploading PDF and extracting text...";
    progressBar.style.width = "25%";
    progressPct.textContent = "25%";

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await apiCall("/generate-quiz-from-pdf", {
            method: "POST",
            body: formData
        });

        progressBar.style.width = "100%";
        progressPct.textContent = "100%";

        const data = await response.json();
        if (response.ok) {
            showToast("Quiz Generated", "Successfully parsed PDF and constructed quiz!");
            loadQuizIntoPlayer(data);
        } else {
            throw new Error(data.error || "PDF Quiz Generation failed.");
        }
    } catch (e) {
        console.error(e);
        showToast("Pipeline Error", e.message || "An unexpected error occurred during PDF parsing.", true);
    } finally {
        btnCancel.disabled = false;
        document.getElementById("btn-cancel-pdf").click();
    }
}

// Generate Quiz from Topic Search
async function handleGenerateTopicQuiz(e) {
    e.preventDefault();
    const topic = document.getElementById("topic-input").value.trim();
    const maxResults = document.getElementById("topic-max-results").value;
    const progressDiv = document.getElementById("topic-progress");
    const btnGenerate = document.getElementById("btn-generate-topic-quiz");

    if (!topic) return;

    progressDiv.classList.remove("hidden");
    btnGenerate.disabled = true;

    try {
        const response = await apiCall("/generate-quiz-from-topic", {
            method: "POST",
            body: JSON.stringify({ topic, max_results: parseInt(maxResults) })
        });

        const data = await response.json();
        if (response.ok) {
            showToast("Quiz Generated", `MCQ quiz generated successfully for: ${topic}`);
            document.getElementById("topic-input").value = "";
            loadQuizIntoPlayer(data);
        } else {
            throw new Error(data.error || "Topic search pipeline rejected.");
        }
    } catch (e) {
        console.error(e);
        showToast("Generation Failed", e.message || "DuckDuckGo or Wikipedia fallback failed.", true);
    } finally {
        progressDiv.classList.add("hidden");
        btnGenerate.disabled = false;
    }
}

// Load dynamic user library in My Quizzes view
async function loadUserLibrary() {
    const container = document.getElementById("library-container");
    const emptyState = document.getElementById("library-empty-state");
    container.innerHTML = "";

    try {
        const response = await apiCall("/quizzes");
        if (response.ok) {
            const data = await response.json();
            const quizzes = data.quizzes || [];

            if (quizzes.length === 0) {
                emptyState.classList.remove("hidden");
                container.classList.add("hidden");
                return;
            }

            emptyState.classList.add("hidden");
            container.classList.remove("hidden");

            quizzes.forEach(quiz => {
                const card = document.createElement("div");
                card.className = "glass-card rounded-2xl p-6 border border-white/5 hover:border-primary/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4";
                
                let sourceIcon = "lightbulb";
                let sourceText = "Topic Search";
                if (quiz.source_type === "video") {
                    sourceIcon = "movie";
                    sourceText = "Video Upload";
                } else if (quiz.source_type === "pdf") {
                    sourceIcon = "picture_as_pdf";
                    sourceText = "PDF Material";
                }

                const createdDate = quiz.created_at ? new Date(quiz.created_at).toLocaleDateString(undefined, {
                    month: 'short', day: 'numeric', year: 'numeric'
                }) : "N/A";

                card.innerHTML = `
                    <div class="flex items-start gap-4">
                        <div class="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-primary-container mt-1 shrink-0">
                            <span class="material-symbols-outlined">${sourceIcon}</span>
                        </div>
                        <div>
                            <h4 class="font-bold text-white text-base">${escapeHtml(quiz.title)}</h4>
                            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant/75 mt-1.5">
                                <span class="flex items-center gap-1"><span class="font-medium">${sourceText}</span></span>
                                <span>•</span>
                                <span>${quiz.question_count} MCQs</span>
                                <span>•</span>
                                <span>G-Eval Score: <strong class="text-primary font-extrabold">${quiz.evaluation_score || "N/A"}</strong></span>
                                <span>•</span>
                                <span>${createdDate}</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 mt-2 sm:mt-0">
                        <button onclick="playQuizFromLibrary('${quiz.id}')" class="px-4 py-2 rounded-xl bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 transition-all flex items-center gap-1.5 active:scale-95">
                            <span class="material-symbols-outlined text-xs">play_arrow</span>
                            <span>Take Quiz</span>
                        </button>
                        <button onclick="deleteQuizFromLibrary(event, '${quiz.id}')" class="p-2 rounded-xl bg-surface-container-high/50 hover:bg-error/10 hover:text-error border border-white/5 transition-all flex items-center justify-center">
                            <span class="material-symbols-outlined text-sm">delete</span>
                        </button>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        console.error(e);
        showToast("Error", "Could not retrieve educational quizzes.", true);
    }
}

// Fetch a single quiz from DB and load into player
async function playQuizFromLibrary(quizId) {
    try {
        const response = await apiCall(`/quiz/${quizId}`);
        if (response.ok) {
            const data = await response.json();
            loadQuizIntoPlayer(data);
        } else {
            showToast("Error", "Could not fetch selected quiz details.", true);
        }
    } catch (e) {
        console.error(e);
        showToast("Connection Error", "API connection failed.", true);
    }
}

// Delete quiz from user library
async function deleteQuizFromLibrary(event, quizId) {
    event.stopPropagation();
    if (!confirm("Are you sure you want to delete this quiz permanently?")) return;

    try {
        const response = await apiCall(`/quiz/${quizId}`, {
            method: "DELETE"
        });

        if (response.ok) {
            showToast("Quiz Deleted", "Successfully removed quiz from database.");
            loadUserLibrary();
            loadDashboardStats();
        } else {
            showToast("Delete Failed", "Could not delete quiz.", true);
        }
    } catch (e) {
        console.error(e);
        showToast("Connection Error", "API deletion request failed.", true);
    }
}

// Load generated/retrieved quiz data into player layout
function loadQuizIntoPlayer(quizData) {
    currentQuiz = quizData;
    userAnswers = {};
    activeQuizTab = "take";

    document.getElementById("active-quiz-title").textContent = quizData.title;
    
    // Set type label
    const typeLabel = document.getElementById("active-quiz-type");
    if (quizData.source_type) {
        typeLabel.textContent = quizData.source_type.toUpperCase() + " GENERATION PIPELINE";
    } else {
        typeLabel.textContent = "EDUCATIONAL CHALLENGE";
    }

    // Load tabs
    switchQuizTab("take");

    // Summary Text
    const summaryText = document.getElementById("quiz-summary-text");
    if (quizData.summary) {
        summaryText.innerHTML = renderMarkdownSimple(quizData.summary);
    } else {
        summaryText.innerHTML = "<p class='text-on-surface-variant/50'>No educational summary available.</p>";
    }

    // Eval Score & Feedback
    const evalScore = document.getElementById("eval-score-circle");
    const evalFeedback = document.getElementById("eval-feedback-text");
    if (quizData.evaluation) {
        evalScore.textContent = quizData.evaluation.score || "N/A";
        evalFeedback.textContent = quizData.evaluation.feedback || "No evaluator feedback.";
    } else {
        evalScore.textContent = "N/A";
        evalFeedback.textContent = "No evaluation metadata generated.";
    }

    // Render questions
    const container = document.getElementById("quiz-questions-container");
    container.innerHTML = "";

    const questions = quizData.questions || [];
    questions.forEach((q, qIndex) => {
        const qCard = document.createElement("div");
        qCard.className = "glass-card rounded-2xl p-6 border border-white/5 space-y-4";
        qCard.id = `q-card-${qIndex}`;

        const optionsHtml = q.options.map((opt, optIndex) => {
            const inputId = `q-${qIndex}-opt-${optIndex}`;
            return `
                <label id="label-${inputId}" class="flex items-center gap-3 p-3 rounded-xl bg-surface-container-low/50 hover:bg-white/5 border border-white/5 cursor-pointer transition-all">
                    <input type="radio" name="question-${qIndex}" value="${escapeHtml(opt)}" id="${inputId}" class="text-primary focus:ring-primary focus:ring-offset-0 bg-transparent border-white/20 w-4 h-4" onclick="selectAnswer(${qIndex}, '${escapeHtml(opt)}')">
                    <span class="text-sm font-medium text-on-surface-variant">${escapeHtml(opt)}</span>
                </label>
            `;
        }).join("");

        qCard.innerHTML = `
            <div class="flex items-start gap-3">
                <span class="w-6 h-6 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0 mt-1">${qIndex + 1}</span>
                <div>
                    <h4 class="font-bold text-white text-base leading-snug">${escapeHtml(q.question)}</h4>
                    <span class="inline-block text-[10px] uppercase font-bold tracking-widest text-primary mt-1">${q.difficulty || "Medium"}</span>
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                ${optionsHtml}
            </div>
            <!-- Explanation Box (Hidden initially) -->
            <div id="explanation-${qIndex}" class="hidden p-4 rounded-xl bg-white/5 border border-white/10 text-xs text-on-surface-variant/80 space-y-1">
                <p class="font-bold text-primary">Explanation:</p>
                <p>${escapeHtml(q.explanation)}</p>
            </div>
        `;
        container.appendChild(qCard);
    });

    // Reset Form buttons
    document.getElementById("btn-submit-quiz").classList.remove("hidden");
    document.getElementById("btn-retake-quiz").classList.add("hidden");
    document.getElementById("quiz-score-banner").classList.add("hidden");

    // Redirect to Player View
    switchView("quiz");
}

// Select radio answer handler
function selectAnswer(qIndex, val) {
    userAnswers[qIndex] = val;
}

// Submit Answers & Grade Quiz
function handleQuizSubmission(e) {
    e.preventDefault();
    if (!currentQuiz) return;

    const questions = currentQuiz.questions || [];
    let correctCount = 0;

    questions.forEach((q, qIndex) => {
        const userVal = userAnswers[qIndex];
        const correctVal = q.answer;
        const qCard = document.getElementById(`q-card-${qIndex}`);
        const explanationBox = document.getElementById(`explanation-${qIndex}`);

        // Display explanation
        explanationBox.classList.remove("hidden");

        // Disable all radio options
        q.options.forEach((opt, optIndex) => {
            const inputId = `q-${qIndex}-opt-${optIndex}`;
            const radio = document.getElementById(inputId);
            const label = document.getElementById(`label-${inputId}`);
            
            if (radio) radio.disabled = true;

            // Clean classes
            label.className = "flex items-center gap-3 p-3 rounded-xl border transition-all text-sm font-medium";

            if (opt === correctVal) {
                // Correct choice (Green)
                label.classList.add("bg-tertiary/10", "border-tertiary", "text-tertiary");
                if (userVal === opt) {
                    label.innerHTML += ` <span class="material-symbols-outlined text-xs ml-auto">check_circle</span>`;
                }
            } else if (userVal === opt) {
                // Incorrect choice selected by user (Red)
                label.classList.add("bg-error/10", "border-error", "text-error");
                label.innerHTML += ` <span class="material-symbols-outlined text-xs ml-auto">cancel</span>`;
            } else {
                // Unselected distractors
                label.classList.add("bg-surface-container-low/30", "border-white/5", "text-on-surface-variant/40");
            }
        });

        if (userVal === correctVal) {
            correctCount++;
            qCard.classList.add("border-tertiary/30");
        } else {
            qCard.classList.add("border-error/30");
        }
    });

    const scorePct = ((correctCount / questions.length) * 100).toFixed(1);
    
    // Display Score Banner
    const scoreText = document.getElementById("quiz-score-text");
    scoreText.textContent = `${correctCount} / ${questions.length} (${scorePct}%)`;
    document.getElementById("quiz-score-banner").classList.remove("hidden");

    // Toggle button views
    document.getElementById("btn-submit-quiz").classList.add("hidden");
    document.getElementById("btn-retake-quiz").classList.remove("hidden");

    showToast("Quiz Evaluated", `You scored ${correctCount}/${questions.length} (${scorePct}%)!`);
}

// Reset taking state for retaking quiz
function handleQuizRetake() {
    if (!currentQuiz) return;
    loadQuizIntoPlayer(currentQuiz);
}

// Handle switching between tabs inside active quiz player
function switchQuizTab(tabId) {
    activeQuizTab = tabId;

    const tabs = ["take", "summary", "eval"];
    tabs.forEach(t => {
        const tabBtn = document.getElementById(`quiz-tab-${t}`);
        const tabContent = document.getElementById(`quiz-tab-content-${t}`);
        
        if (t === tabId) {
            tabBtn.className = "flex-grow py-3 text-center font-bold text-primary border-b-2 border-primary transition-all rounded-lg";
            tabContent.classList.remove("hidden");
        } else {
            tabBtn.className = "flex-grow py-3 text-center font-semibold text-on-surface-variant hover:text-on-surface transition-all rounded-lg";
            tabContent.classList.add("hidden");
        }
    });
}

// Download local JSON copy of quiz
function downloadQuizJSON() {
    if (!currentQuiz) return;
    
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentQuiz, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href",     dataStr);
    downloadAnchor.setAttribute("download", `${currentQuiz.title.replace(/\s+/g, "_")}_quiz.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
}

// Markdown parser helper for summaries
function renderMarkdownSimple(md) {
    if (!md) return "";
    
    // Simple block transformations
    let html = md
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^### (.*?)$/gm, '<h5 class="text-sm font-extrabold text-white mt-4 mb-2">$1</h5>')
        .replace(/^## (.*?)$/gm, '<h4 class="text-base font-extrabold text-white mt-6 mb-3 border-b border-white/5 pb-1">$1</h4>')
        .replace(/^# (.*?)$/gm, '<h3 class="text-lg font-extrabold text-white mt-8 mb-4 border-b border-white/10 pb-2">$1</h3>')
        .replace(/^\s*\-\s*(.*?)$/gm, '<li class="ml-4 list-disc text-xs text-on-surface-variant/80 my-1">$1</li>')
        .replace(/^\s*\*\s*(.*?)$/gm, '<li class="ml-4 list-disc text-xs text-on-surface-variant/80 my-1">$1</li>')
        .replace(/\n/g, '<br>');

    return `<div class="space-y-2">${html}</div>`;
}

// Escape HTML entities to prevent XSS in rendering
function escapeHtml(str) {
    if (!str) return "";
    return str
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
