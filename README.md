# 🧠 CogniScreen — Dementia Cognitive Screening App

**A research-grade cognitive screening tool inspired by the ACE-III (Addenbrooke's Cognitive Examination).**

> ⚠️ For educational and research purposes only. Not a validated clinical diagnostic tool. Always consult a qualified neurologist for clinical assessment.

---

## 📁 Project Structure

```
dementia-app/
├── frontend/
│   ├── index.html          # Landing page
│   ├── login.html          # Authentication
│   ├── register.html       # Registration
│   ├── dashboard.html      # User dashboard with charts
│   ├── cognitive.html      # Cognitive test (multi-section)
│   ├── memory.html         # Visual memory memorization
│   ├── recall.html         # Image recall test
│   ├── speech.html         # Speech recording & analysis
│   ├── result.html         # Full results + delayed recall
│   ├── style.css           # Global styles (dark glassmorphism)
│   └── script.js           # Shared utilities
└── backend/
    ├── app.py              # Flask server (all API routes)
    ├── requirements.txt    # Python dependencies
    └── database.db         # Auto-created SQLite DB
```

---

## 🚀 Setup Instructions

### 1. Prerequisites

- Python 3.8+
- FFmpeg (for audio conversion)

#### Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

Verify: `ffmpeg -version`

---

### 2. Backend Setup

```bash
cd dementia-app/backend

# Create and activate virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install dependencies
pip install flask flask-cors openai-whisper

# Run the backend
python app.py
```

The server starts at **http://localhost:5000**

> **First run:** Whisper will download the `base` model (~142 MB). This is automatic.

---

### 3. Frontend Setup

No build step needed. Just open the HTML files in your browser:

**Option A — Direct (may have CORS issues in some browsers):**
```bash
# Open in browser
open frontend/index.html
```

**Option B — Simple HTTP server (recommended):**
```bash
cd dementia-app/frontend
python -m http.server 8080
# Visit http://localhost:8080
```

**Option C — VS Code Live Server extension** — right-click `index.html` → Open with Live Server.

---

## 🔬 Test Flow

1. **Register / Login** → creates account in SQLite
2. **Cognitive Test** (7 sections):
   - Orientation (day, month, year, season)
   - Place (city, state, country)
   - Attention (serial subtraction: 100−7×5)
   - Word registration & recall (lemon, key, ball)
   - Language (sentence repetition, proverbs)
   - Verbal fluency (letter P, animals — timed)
   - Reasoning & math
3. **Visual Memory** → memorize 5 emoji images in 30 sec
4. **Recall Test** → identify from 16-image grid
5. **Speech Test** → record speech, Whisper transcribes + AI analyzes
6. **Results** → delayed recall + full report + save to DB
7. **Dashboard** → history, trend charts, classification

---

## 📊 Scoring System

| Domain        | Components                                | Weight |
|---------------|-------------------------------------------|--------|
| Cognitive     | Orientation, attention, recall, language  | 33%    |
| Memory        | Visual recall + delayed recall average    | 33%    |
| Speech        | Length, diversity, structure, repetition  | 33%    |

**Classification:**
- ✅ **Low Risk** — Average ≥ 70%
- ⚠️ **Mild Concern** — Average 40–69%
- 🔴 **High Risk** — Average < 40%

---

## 🛠 API Endpoints

| Method | Route                  | Description              |
|--------|------------------------|--------------------------|
| POST   | `/register`            | Create new user          |
| POST   | `/login`               | Authenticate user        |
| POST   | `/saveScore`           | Save test result         |
| GET    | `/getScores/<user_id>` | Get score history        |
| POST   | `/speech`              | Transcribe & analyze audio |
| GET    | `/health`              | Server health check      |

---

## 🎤 Speech Test — Without Microphone

If the microphone is unavailable, use the **text mode** button on the speech page. Type your response and click "Analyze Text" for local text-based scoring.

---

## 🔧 Troubleshooting

**Backend won't start:**
- Ensure you're using Python 3.8+ (`python --version`)
- Install all dependencies: `pip install flask flask-cors openai-whisper`

**Speech transcription fails:**
- Make sure FFmpeg is installed and in PATH
- Try text mode as fallback

**CORS errors in browser:**
- Use the `python -m http.server` method instead of opening files directly

**Whisper takes long to load:**
- First run downloads model (~142 MB). Subsequent runs are fast.

---

## 📚 Clinical Background

This app is inspired by the **ACE-III Indian English** edition, which assesses:
- Attention (orientation, serial subtraction)
- Memory (word and name/address recall)
- Fluency (letter and animal naming)
- Language (repetition, naming, commands)
- Visuospatial (not implemented in digital form)

**Reference:** Addenbrooke's Cognitive Examination III — Indian English version (updated 07/03/2013)

---

## 🧰 Tech Stack

| Layer    | Technology                    |
|----------|-------------------------------|
| Frontend | HTML5, CSS3, Vanilla JS       |
| Charts   | Chart.js 4.4                  |
| Backend  | Python Flask                  |
| Database | SQLite3                       |
| AI/STT   | OpenAI Whisper (local)        |
| Audio    | FFmpeg (webm→wav conversion)  |
| Fonts    | DM Serif Display + DM Sans    |
