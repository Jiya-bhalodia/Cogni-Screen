"""
CogniScreen - Flask Backend
Dementia Cognitive Screening App
Now using Supabase (Postgres) instead of SQLite
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import hashlib
# subprocess no longer needed — Groq Whisper accepts audio directly
import tempfile
import re
import urllib.request
from collections import Counter

app = Flask(__name__)
CORS(app, origins='*', methods=['GET','POST','OPTIONS'], allow_headers=['Content-Type'])

# ── Supabase config ───────────────────────────────────────────────────────────
SUPABASE_URL = 'https://ywvwhiqegdbwolmhzfog.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl3dndoaXFlZ2Rid29sbWh6Zm9nIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY2MjUxMTEsImV4cCI6MjA5MjIwMTExMX0.t1LWvCCQj7WHBDC1RXSCY_354m_RnyObQvJE-3OL_N0'

def sb_headers():
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

def sb_get(table, params=''):
    url = f'{SUPABASE_URL}/rest/v1/{table}?{params}'
    req = urllib.request.Request(url, headers=sb_headers(), method='GET')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def sb_post(table, data):
    url = f'{SUPABASE_URL}/rest/v1/{table}'
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, headers=sb_headers(), method='POST')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def sb_patch(table, params, data):
    url = f'{SUPABASE_URL}/rest/v1/{table}?{params}'
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, headers=sb_headers(), method='PATCH')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── Groq config ───────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_URL     = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL   = 'llama-3.3-70b-versatile'

def groq_chat(prompt, max_tokens=800):
    payload = json.dumps({
        'model': GROQ_MODEL,
        'max_tokens': max_tokens,
        'temperature': 0.1,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode()
    req = urllib.request.Request(
        GROQ_URL, data=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content'].strip()

# ── Groq Whisper ─────────────────────────────────────────────────────────────
GROQ_WHISPER_URL = 'https://api.groq.com/openai/v1/audio/transcriptions'

def groq_transcribe(audio_path):
    """Send audio to Groq Whisper, get transcript + word timestamps."""
    import requests
    with open(audio_path, 'rb') as f:
        audio_data = f.read()

    print(f"[Whisper] Sending {len(audio_data)} bytes to Groq...")
    response = requests.post(
        GROQ_WHISPER_URL,
        headers={'Authorization': f'Bearer {GROQ_API_KEY}'},
        files={'file': ('audio.webm', audio_data, 'audio/webm')},
        data={
            'model': 'whisper-large-v3-turbo',
            'response_format': 'verbose_json',
            'timestamp_granularities[]': 'word',
            'language': 'en'
        },
        timeout=30
    )
    print(f"[Whisper] Response status: {response.status_code}")
    if response.status_code != 200:
        print(f"[Whisper] Error body: {response.text}")
        raise RuntimeError(f"Groq Whisper error {response.status_code}: {response.text}")
    result = response.json()
    print(f"[Whisper] OK — transcript: '{result.get('text','')[:60]}...' words: {len(result.get('words',[]))}")
    return result

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/register', methods=['POST','OPTIONS'])
def register():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json()
    name     = (data.get('name') or '').strip()
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not email or not password:
        return jsonify({'success': False, 'error': 'All fields are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters.'}), 400

    # Check duplicate email
    try:
        existing = sb_get('users', f'email=eq.{email}&select=id')
        if existing:
            return jsonify({'success': False, 'error': 'An account with this email already exists.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

    try:
        rows = sb_post('users', {
            'name': name,
            'email': email,
            'password_hash': hash_password(password)
        })
        user = rows[0]
        return jsonify({'success': True, 'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/login', methods=['POST','OPTIONS'])
def login():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data  = request.get_json()
    email = (data.get('email') or '').strip().lower()
    pw    = data.get('password') or ''

    try:
        rows = sb_get('users', f'email=eq.{email}&password_hash=eq.{hash_password(pw)}&select=id,name,email')
        if not rows:
            return jsonify({'success': False, 'error': 'Invalid email or password.'}), 401
        user = rows[0]
        return jsonify({'success': True, 'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Scores ────────────────────────────────────────────────────────────────────
@app.route('/saveScore', methods=['POST','OPTIONS'])
def save_score():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id required'}), 400
    try:
        sb_post('test_results', {
            'user_id':         int(user_id),
            'cognitive_score': int(data.get('cognitive_score', 0)),
            'memory_score':    int(data.get('memory_score', 0)),
            'speech_score':    int(data.get('speech_score', 0)),
            'transcript':      data.get('transcript', '')
        })
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/getScores/<int:user_id>', methods=['GET','OPTIONS'])
def get_scores(user_id):
    if request.method == 'OPTIONS': return jsonify({}), 200
    try:
        rows = sb_get('test_results',
            f'user_id=eq.{user_id}&order=timestamp.desc&limit=50'
            '&select=id,user_id,cognitive_score,memory_score,speech_score,transcript,timestamp'
        )
        return jsonify({'success': True, 'results': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── AI Scoring (Groq) ─────────────────────────────────────────────────────────
@app.route('/scoreAnswers', methods=['POST','OPTIONS'])
def score_answers():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json()

    word_recall      = data.get('word_recall', [])
    chosen_words     = data.get('chosen_words', [])
    sentence_typed   = data.get('sentence_typed', '')
    sentence_correct = data.get('sentence_correct', '')
    fluency_letter   = data.get('fluency_letter', '')
    fluency_words    = data.get('fluency_words', '')
    animal_words     = data.get('animal_words', '')
    city             = data.get('city', '')
    state            = data.get('state', '')
    country          = data.get('country', '')

    prompt = f"""You are a clinical cognitive screening assistant scoring a patient's answers from an ACE-III inspired test.
Be fair, generous with minor typos, and strict on clearly wrong answers.
Respond ONLY with valid JSON — no markdown, no explanation outside the JSON.

1. WORD RECALL
Correct words: {chosen_words}
Patient typed: {word_recall}
- Accept clear typos (e.g. "BAAL" for "BALL")
- Accept phonetically close answers
- Score each word 1 if correct/close, 0 if wrong
Return: {{"word_recall": [1,0,1], "word_recall_total": 2, "word_recall_feedback": "Got 2/3 words."}}

2. SENTENCE REPETITION
Correct: "{sentence_correct}"
Patient typed: "{sentence_typed}"
- Score 2 if essentially correct (1-2 minor typos ok)
- Score 1 if roughly correct but words missing/changed
- Score 0 if very different
Return: {{"sentence_score": 2, "sentence_feedback": "Repeated correctly."}}

3. VERBAL FLUENCY — LETTER "{fluency_letter}"
Patient listed: "{fluency_words}"
- Count only real English words starting with "{fluency_letter}"
- Ignore proper nouns, duplicates, gibberish
Return: {{"fluency_letter_valid": 8, "fluency_letter_feedback": "8 valid words."}}

4. ANIMAL FLUENCY
Patient listed: "{animal_words}"
- Count only real animals, accept spelling mistakes
- Ignore duplicates and non-animals
Return: {{"fluency_animals_valid": 11, "fluency_animals_feedback": "11 valid animals."}}

5. PLACE ORIENTATION
City: "{city}", State: "{state}", Country: "{country}"
- Score 1 each if looks like a real place name (not gibberish)
- Score 0 only if clearly nonsense (e.g. "xxx", single chars)
Return: {{"place_city": 1, "place_state": 1, "place_country": 1, "place_feedback": "All places provided."}}

Return one combined JSON object with all keys."""

    try:
        raw     = groq_chat(prompt)
        cleaned = raw.replace('```json','').replace('```','').strip()
        result  = json.loads(cleaned)
        result['success']    = True
        result['ai_scored']  = True
        return jsonify(result)
    except Exception as e:
        print(f"[Groq] Error: {e} — using fallback")
        return jsonify(basic_score_fallback(
            word_recall, chosen_words, sentence_typed, sentence_correct,
            fluency_letter, fluency_words, animal_words, city, state, country
        ))


def basic_score_fallback(word_recall, chosen_words, sentence_typed, sentence_correct,
                          fluency_letter, fluency_words, animal_words, city, state, country):
    word_scores = []
    for typed in word_recall:
        matched = any(levenshtein(typed.strip().upper(), c.upper()) <= 2 for c in chosen_words)
        word_scores.append(1 if matched else 0)

    r    = sentence_typed.lower().replace(r'[^a-z ]','').strip()
    dist = levenshtein(r, sentence_correct.lower())
    sentence_score = 2 if dist <= 2 else (1 if dist <= 6 else 0)

    lwords = [w.strip().lower() for w in fluency_words.split(',') if w.strip()]
    valid_letter = len(set([w for w in lwords if w.startswith(fluency_letter.lower()) and len(w) > 1]))

    awords = [w.strip().lower() for w in animal_words.split(',') if len(w.strip()) > 1]
    valid_animals = len(set(awords))

    return {
        'success': True, 'ai_scored': False,
        'word_recall': word_scores,
        'word_recall_total': sum(word_scores),
        'word_recall_feedback': f'Got {sum(word_scores)}/3 words.',
        'sentence_score': sentence_score,
        'sentence_feedback': 'Scored by text similarity.',
        'fluency_letter_valid': valid_letter,
        'fluency_letter_feedback': f'{valid_letter} valid words starting with {fluency_letter}.',
        'fluency_animals_valid': valid_animals,
        'fluency_animals_feedback': f'{valid_animals} animals listed.',
        'place_city': 1 if len(city.strip()) > 1 else 0,
        'place_state': 1 if len(state.strip()) > 1 else 0,
        'place_country': 1 if len(country.strip()) > 1 else 0,
        'place_feedback': 'Place answers checked.'
    }


def levenshtein(a, b):
    m, n = len(a), len(b)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): dp[i][0] = i
    for j in range(n+1): dp[0][j] = j
    for i in range(1, m+1):
        for j in range(1, n+1):
            dp[i][j] = dp[i-1][j-1] if a[i-1]==b[j-1] else 1+min(dp[i-1][j-1],dp[i-1][j],dp[i][j-1])
    return dp[m][n]


# ── Speech Route (Groq Whisper with word timestamps) ─────────────────────────
@app.route('/speech', methods=['POST','OPTIONS'])
def speech():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if 'audio' not in request.files:
        return jsonify({'success': False, 'error': 'No audio file'}), 400

    audio_file = request.files['audio']
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
        audio_file.save(tmp.name)
        audio_path = tmp.name

    try:
        result     = groq_transcribe(audio_path)
        transcript = result.get('text', '').strip()
        words      = result.get('words', [])      # [{word, start, end}, ...]
        duration   = result.get('duration', 0)    # total seconds
        analysis   = analyze_speech_clinical(transcript, words, duration)
        return jsonify({'success': True, 'transcript': transcript, **analysis})
    except Exception as e:
        print(f"[Speech] Error: {e}")
        return jsonify({'success': False, 'error': str(e),
                        'hint': 'Make sure GROQ_API_KEY is set.'}), 500
    finally:
        try: os.unlink(audio_path)
        except: pass


def analyze_speech_clinical(transcript, words, duration):
    """
    Extract clinical speech markers from Groq Whisper word timestamps.
    Detects: speech rate, pauses, stutters, filler words, vocabulary diversity.
    """
    # ── Single-word fillers ───────────────────────────────────────────────────
    WORD_FILLERS = {
        'uh','um','uhh','umm','hmm','hm','er','erm','ah','ahh',
        'oh','ooh','eh','huh','mhm','aha','okay','ok','right',
        'yeah','yep','so','well','like','basically','literally',
        'actually','honestly','seriously','clearly','obviously'
    }
    # ── Multi-word filler phrases ─────────────────────────────────────────────
    PHRASE_FILLERS = [
        'you know', 'i mean', 'kind of', 'sort of', 'i think',
        'you see', 'i guess', 'i suppose', 'what i mean', 'to be honest',
        'if you will', 'as i said', 'at the end of the day'
    ]

    if not transcript or not transcript.strip():
        return {
            'score': 10, 'word_count': 0, 'unique_words': 0,
            'feedback': 'No speech detected. Please try again.',
            'markers': build_markers(0, 0, 0, 0, 0, 0)
        }

    text_lower = transcript.lower()

    # ── Count phrase fillers first (before splitting into words) ─────────────
    phrase_filler_count = 0
    for phrase in PHRASE_FILLERS:
        count = text_lower.count(phrase)
        phrase_filler_count += count

    # ── Word-level stats ──────────────────────────────────────────────────────
    clean = [re.sub(r'[^a-z]','', w) for w in text_lower.split()]
    clean = [w for w in clean if w]
    total  = len(clean)
    unique = len(set(clean))

    # Count single-word fillers
    word_filler_count = sum(1 for w in clean if w in WORD_FILLERS)
    filler_count = word_filler_count + phrase_filler_count

    # ── Repeated words/phrases (consecutive) ─────────────────────────────────
    # Check text-level repetition — same word appearing 3+ times
    freq = Counter(clean)
    repeated_words = [w for w, c in freq.most_common() if c >= 3 and len(w) > 2 and w not in {'and','the','to','a','i','of','in','that','it','is','was'}]

    pauses        = []
    long_pauses   = 0
    stutter_count = 0
    speech_rate   = 0

    if words and len(words) > 1:
        first_word_start = words[0].get('start', 0)
        last_word_end    = words[-1].get('end', 0)
        actual_span      = last_word_end - first_word_start

        for i in range(1, len(words)):
            prev_end   = words[i-1].get('end',   0)
            curr_start = words[i].get('start',   0)
            gap        = round(curr_start - prev_end, 3)

            # Pause thresholds:
            # > 0.5s = notable hesitation (normal breath is ~0.2s)
            # > 1.5s = clinically significant long pause
            if gap > 0.5:
                pauses.append(gap)
            if gap > 1.5:
                long_pauses += 1

            # Stutter: same word within 1s gap
            w1 = re.sub(r'[^a-z]','', words[i-1].get('word','').lower())
            w2 = re.sub(r'[^a-z]','', words[i].get('word','').lower())
            if w1 and w1 == w2 and gap < 1.0:
                stutter_count += 1

        if actual_span > 0:
            speech_rate = round((total / actual_span) * 60)

    avg_pause = round(sum(pauses)/len(pauses), 2) if pauses else 0

    # ── Clinical scoring ──────────────────────────────────────────────────────
    score     = 100
    concerns  = []
    positives = []

    # 1. Speech rate
    if speech_rate > 0:
        if speech_rate < 80:
            score -= 25
            concerns.append(f'Very slow speech rate ({speech_rate} wpm) — significant word-finding difficulty likely.')
        elif speech_rate < 110:
            score -= 12
            concerns.append(f'Below-normal speech rate ({speech_rate} wpm) — mild hesitancy detected.')
        elif speech_rate > 200:
            concerns.append(f'Rapid speech ({speech_rate} wpm) — may affect clarity.')
        else:
            positives.append(f'Normal speech rate ({speech_rate} wpm).')

    # 2. Long pauses (> 1.5s)
    if long_pauses >= 4:
        score -= 25
        concerns.append(f'{long_pauses} long pauses (>1.5s) — significant hesitation, possible word-finding impairment.')
    elif long_pauses >= 2:
        score -= 15
        concerns.append(f'{long_pauses} long pauses detected — word-finding difficulty observed.')
    elif long_pauses == 1:
        score -= 8
        concerns.append('1 significant pause (>1.5s) detected.')
    else:
        positives.append('No significant long pauses.')

    # 3. General hesitations (> 0.5s)
    if len(pauses) >= 6:
        score -= 10
        concerns.append(f'Frequent hesitations ({len(pauses)} pauses >0.5s) — effortful, non-fluent speech.')
    elif len(pauses) >= 3:
        score -= 5
        concerns.append(f'Some hesitations noted ({len(pauses)} pauses).')

    # 4. Stutters
    if stutter_count >= 3:
        score -= 20
        concerns.append(f'{stutter_count} word repetitions — possible stuttering or word-retrieval difficulty.')
    elif stutter_count >= 1:
        score -= 8
        concerns.append(f'{stutter_count} word repetition(s) detected.')

    # 5. Filler words + phrases
    filler_ratio = filler_count / max(total, 1)
    if filler_count >= 4 or filler_ratio > 0.1:
        score -= 20
        concerns.append(f'High filler usage ({filler_count} instances: filler words/phrases like "um", "you know", "like") — significant speech hesitancy.')
    elif filler_count >= 2 or filler_ratio > 0.05:
        score -= 8
        concerns.append(f'Moderate filler usage ({filler_count} instances) — some hesitancy noted.')
    else:
        positives.append('Minimal filler words.')

    # 6. Repeated words (content repetition)
    if repeated_words:
        score -= 8
        concerns.append(f'Word repetition detected ("{", ".join(repeated_words[:2])}") — may indicate limited vocabulary or perseveration.')

    # 7. Vocabulary diversity
    div = unique / total if total else 0
    if div > 0.75:
        positives.append('Rich and varied vocabulary.')
    elif div > 0.55:
        positives.append('Adequate vocabulary diversity.')
    else:
        score -= 10
        concerns.append('Reduced vocabulary diversity — possible word-finding difficulty.')

    # 8. Response length
    if total < 15:
        score -= 10
        concerns.append('Short response — limited speech output may indicate difficulty.')
    elif total >= 50:
        positives.append('Good response length.')

    score = max(0, min(100, score))
    feedback_str = ' '.join(concerns + positives) or 'Speech analysis complete.'

    return {
        'score':        score,
        'feedback':     feedback_str,
        'word_count':   total,
        'unique_words': unique,
        'markers':      build_markers(speech_rate, long_pauses, stutter_count,
                                      filler_count, avg_pause, len(pauses))
    }


def build_markers(speech_rate, long_pauses, stutters, fillers, avg_pause, total_pauses):
    return {
        'speech_rate':  speech_rate,
        'long_pauses':  long_pauses,
        'total_pauses': total_pauses,
        'avg_pause':    avg_pause,
        'stutters':     stutters,
        'fillers':      fillers,
    }


# ── Health ────────────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'db': 'supabase', 'speech': 'groq-whisper'})


if __name__ == '__main__':
    # Check critical config
    if GROQ_API_KEY == 'YOUR_GROQ_KEY_HERE':
        print("\n⚠️  WARNING: GROQ_API_KEY is not set!")
        print("   Speech analysis and AI scoring will fail.")
        print("   Run with: GROQ_API_KEY=gsk_xxx python app.py\n")
    print("\n" + "="*52)
    print("  CogniScreen Backend — http://localhost:5001")
    print("  Database : Supabase (cloud Postgres)")
    print("  Speech   : Groq Whisper (word timestamps)")
    print(f"  Groq Key : {'SET ✓' if GROQ_API_KEY != 'YOUR_GROQ_KEY_HERE' else 'NOT SET ✗'}")
    print("="*52 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5001)