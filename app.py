from flask import Flask, request, jsonify, render_template, send_from_directory, Response, stream_with_context
import paho.mqtt.client as mqtt
from flask_cors import CORS
import sqlite3, os, json, requests, tempfile, threading, re
from faster_whisper import WhisperModel
from datetime import datetime

app = Flask(__name__)
CORS(app)

DEPARTMENT_MAP = {
    "Orthopedics": {"ml": "ഓർത്തോപീഡിക്സ് വിഭാഗം — അസ്ഥി, സന്ധി, പേശി സംബന്ധിത രോഗങ്ങൾ", "hi": "हड्डी विभाग", "en": "Orthopedics — Bone, Joint and Muscle"},
    "Cardiology": {"ml": "ഹൃദ്രോഗ വിഭാഗം — ഹൃദയ സംബന്ധിത രോഗങ്ങൾ", "hi": "हृदय विभाग", "en": "Cardiology — Heart and Cardiovascular"},
    "General Medicine": {"ml": "ജനറൽ മെഡിസിൻ — പൊതു രോഗങ്ങൾ", "hi": "सामान्य चिकित्सा", "en": "General Medicine"},
    "ENT": {"ml": "ENT വിഭാഗം — ചെവി, മൂക്ക്, തൊണ്ട", "hi": "कान नाक गला विभाग", "en": "ENT — Ear, Nose and Throat"},
    "Gastroenterology": {"ml": "ഗ്യാസ്ട്രോ വിഭാഗം — ദഹന സംബന്ധിത രോഗങ്ങൾ", "hi": "पाचन विभाग", "en": "Gastroenterology — Digestive System"},
    "Pulmonology": {"ml": "ശ്വാസകോശ വിഭാഗം — ശ്വസന സംബന്ധിത രോഗങ്ങൾ", "hi": "फेफड़े विभाग", "en": "Pulmonology — Lungs and Breathing"},
    "Neurology": {"ml": "ന്യൂറോളജി വിഭാഗം — തലച്ചോർ, നാഡി സംബന്ധിത രോഗങ്ങൾ", "hi": "तंत्रिका विभाग", "en": "Neurology — Brain and Nervous System"},
    "Dermatology": {"ml": "ചർമ്മ വിഭാഗം — ത്വക്ക് സംബന്ധിത രോഗങ്ങൾ", "hi": "त्वचा विभाग", "en": "Dermatology — Skin"},
    "Pediatrics": {"ml": "ശിശു വിഭാഗം — കുട്ടികളുടെ രോഗങ്ങൾ", "hi": "बाल रोग विभाग", "en": "Pediatrics — Children"},
    "Gynecology": {"ml": "സ്ത്രീരോഗ വിഭാഗം", "hi": "स्त्री रोग विभाग", "en": "Gynecology"},
    "Urology": {"ml": "യൂറോളജി വിഭാഗം — മൂത്രനാളി സംബന്ധിത രോഗങ്ങൾ", "hi": "मूत्र विभाग", "en": "Urology"},
    "Ophthalmology": {"ml": "നേത്ര വിഭാഗം — കണ്ണ് സംബന്ധിത രോഗങ്ങൾ", "hi": "नेत्र विभाग", "en": "Ophthalmology — Eyes"},
    "Psychiatry": {"ml": "മാനസികാരോഗ്യ വിഭാഗം", "hi": "मानसिक स्वास्थ्य विभाग", "en": "Psychiatry — Mental Health"},
    "Emergency": {"ml": "അടിയന്തര വിഭാഗം — ഉടനടി ശ്രദ്ധ ആവശ്യം", "hi": "आपातकालीन विभाग", "en": "Emergency — Immediate Attention Required"},
}

def get_department_message(department, token, language):
    dept_info = DEPARTMENT_MAP.get(department, DEPARTMENT_MAP["General Medicine"])
    dept_text = dept_info.get(language, dept_info["en"])
    msgs = {
        "ml": f"നന്ദി. നിങ്ങളുടെ ടോക്കൺ നമ്പർ {token} ആണ്. നിങ്ങളെ {dept_text} വിഭാഗത്തിലേക്ക് നിയോഗിച്ചിരിക്കുന്നു. ദയവായി അവിടെ കാത്തിരിക്കൂ.",
        "hi": f"धन्यवाद. आपका टोकन {token} है. आपको {dept_text} में भेजा गया है. कृपया वहां प्रतीक्षा करें।",
        "en": f"Thank you. Your token is {token}. You have been assigned to {dept_text}. Please proceed there and wait."
    }
    return msgs.get(language, msgs["en"])


OLLAMA_URL    = "http://localhost:11434/api/chat"
FAST_MODEL    = "gemma4:e2b-it-q4_K_M"
QUALITY_MODEL = "gemma4:e2b-it-q4_K_M"
WHISPER_PATH  = "/home/rasp/whisper-small"
DB_PATH       = "/home/rasp/kiosk/db/kiosk.db"
AUDIO_DIR     = "/home/rasp/kiosk/static/audio"

# Load Whisper tiny for speed
print("Loading Whisper...")
whisper_model = WhisperModel(WHISPER_PATH, device="cpu", compute_type="int8", num_workers=2)
print("Whisper ready")

SYSTEM_PROMPT = """You are a clinical intake assistant at Koode, a hospital in Kerala.
Collect the patient symptom history through smart clinical questions then assign the correct department.

CRITICAL LANGUAGE RULE:
- If patient selected Malayalam: respond ONLY in Malayalam script. Never use English or Hindi words.
- If patient selected Hindi: respond ONLY in Hindi script. Never use English or Malayalam words.
- If patient selected English: respond ONLY in English. Never use Malayalam or Hindi words.
- Detect language from the session, not from what patient types.
- Even if patient types in English, respond in their selected session language.

INTERVIEW FLOW:
1. Ask name and age
2. Ask main complaint today
3. Ask symptom-specific follow-ups based on what they say:
   - Pain: location, character, radiation, timing, severity 1-10
   - Fever: duration, pattern, chills, rash, joint pain
   - Cough: duration, sputum colour, blood, breathlessness
   - Vomiting: frequency, blood, last meal, associated pain
   - Let their answers guide your questions
4. Ask relevant past history only
5. Ask current medications and allergies
6. Maximum 12 questions then generate report

DEPARTMENT ASSIGNMENT RULES:
- Bone/joint/muscle/fracture/back pain → Orthopedics
- Chest pain/heart/palpitations → Cardiology
- Ear/nose/throat/hearing → ENT
- Stomach/liver/bowel/vomiting/diarrhea → Gastroenterology
- Cough/breathing/lungs/TB → Pulmonology
- Headache/seizure/paralysis/numbness → Neurology
- Skin/rash/itching → Dermatology
- Child under 12 → Pediatrics
- Female reproductive → Gynecology
- Eye problems → Ophthalmology
- Urinary problems → Urology
- Emergency/severe → Emergency
- General fever/cold/flu → General Medicine

STRICT RULES:
- Never ask about address, occupation, mental health unless presenting complaint
- One question per response, under 12 words
- 2-3 word acknowledgement then question
- Never give medical advice or disclaimers
- After 12 exchanges output CLINICAL_REPORT JSON

CLINICAL_REPORT:{"name":"","age":"","gender":"","complaint":"","duration":"","onset":"sudden/gradual","severity":"X/10","character":"","location":"","associated":[],"aggravating":"","relieving":"","history":"","medications":"","allergies":"","urgency":"LOW/MEDIUM/HIGH/EMERGENCY","department":"General Medicine","investigations":[],"summary":"3 sentence clinical paragraph in English"}"""

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        name TEXT DEFAULT '',
        age TEXT DEFAULT '',
        gender TEXT DEFAULT '',
        language TEXT DEFAULT 'ml',
        status TEXT DEFAULT 'interviewing',
        conversation TEXT DEFAULT '[]',
        clinical_report TEXT DEFAULT '',
        full_report TEXT DEFAULT '',
        prescription TEXT DEFAULT '',
        lab_orders TEXT DEFAULT '',
        vitals TEXT DEFAULT '{}',
        created_at TEXT,
        updated_at TEXT
    )''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

MQTT_BROKER = "localhost"
MQTT_PORT   = 1883
MQTT_TOPIC_BOT = "koode/bot/navigate"

def mqtt_publish(topic, payload):
    try:
        print(f"[MQTT] Publishing to {topic}:")
        print(f"[MQTT] {json.dumps(payload, ensure_ascii=False)}")
        client = mqtt.Client()
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(topic, json.dumps(payload), qos=1)
        client.disconnect()
        print(f"[MQTT] Published successfully")
    except Exception as e:
        print(f"[MQTT ERROR] {e}")

def generate_token():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM patients WHERE date(created_at)=date('now')").fetchone()[0]
    conn.close()
    return f"K{datetime.now().strftime('%m%d')}{count+1:03d}"

def chat_ollama(messages, stream=False):
    payload = {
        "model": FAST_MODEL,
        "messages": [
            {"role": "user", "content": "You are filling a hospital intake form. Only ask symptom questions. No advice. Confirm."},
            {"role": "assistant", "content": "Understood. I will only ask clinical symptom questions one at a time."}
        ] + messages,
        "system": SYSTEM_PROMPT,
        "stream": stream,
        "keep_alive": -1,
        "think": False,
        "options": {
            "num_ctx": 2048,
            "temperature": 0.1,
            "num_thread": 4,
            "num_predict": 150
        }
    }
    return requests.post(OLLAMA_URL, json=payload, timeout=180, stream=stream)

def generate_full_report(conversation, token):
    # Only send last 10 messages to keep prompt small
    recent = conversation[-10:] if len(conversation) > 10 else conversation
    prompt = f"""Write a concise clinical report in plain text (no markdown, no bullet points, no asterisks) for a doctor based on this patient intake:

{json.dumps(recent, ensure_ascii=False)}

Write 2 paragraphs:
Paragraph 1: Patient presentation — who they are, main complaint, duration, severity, associated symptoms.
Paragraph 2: Relevant history, medications, allergies, recommended investigations and urgency.

Plain text only. No headers. No bullets. No formatting symbols."""
    
    payload = {
        "model": QUALITY_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": -1,
        "think": False,
        "options": {"num_ctx": 4096, "temperature": 0.1, "num_thread": 4, "num_predict": 600}
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=600)
        report = r.json()["message"]["content"].strip()
        # Strip markdown formatting
        report = re.sub(r"#{1,6} ?", "", report)
        report = re.sub(r"[*_`]+", "", report)
        report = report.strip()
        print(f"[REPORT] Generated {len(report)} chars for {token}")
        conn = get_db()
        conn.execute("UPDATE patients SET full_report=?, status=?, updated_at=? WHERE token=?",
                    (report, "ready", datetime.now().isoformat(), token))
        conn.commit()
        conn.close()
        print(f"[REPORT] Saved to DB, status=ready for {token}")
    except Exception as e:
        import traceback
        print(f"[REPORT ERROR] {token}: {e}")
        traceback.print_exc()

def transcribe_audio(filepath, language=None):
    try:
        import subprocess
        wav_path = filepath + ".wav"
        subprocess.run([
            "ffmpeg", "-i", filepath, "-ar", "16000", "-ac", "1",
            "-f", "wav", wav_path, "-y", "-loglevel", "quiet"
        ], check=True)
        # Force language — never auto detect
        # ml = Malayalam, hi = Hindi, en = English
        lang = language if language in ["ml", "hi", "en"] else "ml"
        segments, info = whisper_model.transcribe(
            wav_path,
            language=lang,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            without_timestamps=True,
            task="transcribe"  # never translate, always transcribe in same language
        )
        text = " ".join([s.text for s in segments]).strip()
        print(f"STT [{lang}]: {text[:80]}")
        try:
            os.unlink(wav_path)
        except: pass
        return text, lang
    except Exception as e:
        print(f"Transcribe error: {e}")
        return "", "unknown"

def warmup():
    try:
        requests.post("http://localhost:11434/api/generate",
            json={"model": FAST_MODEL, "prompt": "", "keep_alive": -1}, timeout=120)
        print("Model warmed up")
    except: pass

@app.route("/")
def index():
    return render_template("kiosk.html")

@app.route("/doctor")
def doctor():
    return render_template("doctor.html")

@app.route("/static/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route("/api/start", methods=["POST"])
def start_session():
    data = request.json
    language = data.get("language", "ml")
    token = generate_token()
    now = datetime.now().isoformat()
    greetings = {
        "ml": "നമസ്കാരം. ഞാൻ Koode ആശുപത്രിയിലെ ഡിജിറ്റൽ സഹായി ആണ്. നിങ്ങളുടെ പേരും പ്രായവും പറയൂ.",
        "hi": "नमस्ते. मैं Koode अस्पताल का डिजिटल सहायक हूं. कृपया अपना नाम और उम्र बताएं।",
        "en": "Hello. I am the Koode Hospital digital assistant. Please tell me your name and age."
    }
    greeting = greetings.get(language, greetings["en"])
    conversation = [{"role": "assistant", "content": greeting}]
    conn = get_db()
    conn.execute("INSERT INTO patients (token, language, conversation, created_at, updated_at) VALUES (?,?,?,?,?)",
                (token, language, json.dumps(conversation), now, now))
    conn.commit()
    conn.close()
    return jsonify({"token": token, "message": greeting})

@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    data = request.json
    token = data.get("token")
    message = data.get("message", "").strip()
    if not message or not token:
        return jsonify({"error": "Missing data"}), 400

    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE token=?", (token,)).fetchone()
    if not patient:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    language = patient["language"]
    conversation = json.loads(patient["conversation"])
    conversation.append({"role": "user", "content": message})
    conn.close()

    def generate():
        full_response = ""
        try:
            r = chat_ollama(conversation, stream=True)
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token_text = chunk.get("message", {}).get("content", "")
                        if token_text:
                            full_response_parts.append(token_text)
                            yield f"data: {json.dumps({'token': token_text})}\n\n"
                        if chunk.get("done"):
                            break
                    except: pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        full_response = "".join(full_response_parts)
        is_complete = "CLINICAL_REPORT:" in full_response
        clean_response = full_response

        if is_complete:
            try:
                json_str = full_response.split("CLINICAL_REPORT:")[1].strip()
                quick = json.loads(json_str)
                clean_response = {
                    "ml": f"നന്ദി. നിങ്ങളുടെ ടോക്കൺ {token} ആണ്. ഡോക്ടർ ഉടൻ വിളിക്കും.",
                    "hi": f"धन्यवाद. आपका टोकन {token} है. डॉक्टर जल्द बुलाएंगे।",
                    "en": f"Thank you. Your token is {token}. The doctor will call you shortly."
                }.get(language, f"Token: {token}")
                conn2 = get_db()
                conn2.execute("UPDATE patients SET clinical_report=?, status=?, updated_at=? WHERE token=?",
                            (json.dumps(quick), "processing", datetime.now().isoformat(), token))
                conn2.commit()
                conn2.close()
                threading.Thread(target=generate_full_report, args=(conversation, token), daemon=True).start()
            except Exception as e:
                print(f"Report parse error: {e}")

        conversation.append({"role": "assistant", "content": clean_response})
        conn3 = get_db()
        conn3.execute("UPDATE patients SET conversation=?, updated_at=? WHERE token=?",
                    (json.dumps(conversation), datetime.now().isoformat(), token))
        conn3.commit()
        conn3.close()
        yield f"data: {json.dumps({'done': True, 'full': clean_response, 'complete': is_complete})}\n\n"

    full_response_parts = []
    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                   headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    token = data.get("token")
    message = data.get("message", "").strip()
    if not token:
        return jsonify({"error": "Missing token"}), 400

    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE token=?", (token,)).fetchone()
    if not patient:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    language = patient["language"]
    conversation = json.loads(patient["conversation"])
    conversation.append({"role": "user", "content": message})

    # Inject language enforcement as first message
    lang_instruction = {
        "ml": "ഈ സംഭാഷണം മുഴുവൻ മലയാളത്തിൽ മാത്രം നടത്തുക. ഒരു വാക്കുപോലും ഇംഗ്ലീഷിൽ ഉപയോഗിക്കരുത്.",
        "hi": "यह पूरी बातचीत केवल हिंदी में करें। एक भी शब्द अंग्रेजी में न बोलें।",
        "en": "Conduct this entire conversation in English only."
    }.get(language, "Conduct this entire conversation in English only.")
    
    conversation_with_lang = [
        {"role": "user", "content": lang_instruction},
        {"role": "assistant", "content": {"ml": "ശരി, ഞാൻ മലയാളത്തിൽ മാത്രം സംസാരിക്കാം.", "hi": "ठीक है, मैं केवल हिंदी में बात करूंगा।", "en": "Understood, I will respond in English only."}.get(language, "Understood.")}
    ] + conversation

    try:
        r = chat_ollama(conversation_with_lang, stream=False)
        result = r.json()
        response = result["message"]["content"].strip()
        if not response:
            thinking = result["message"].get("thinking", "")
            lines = [l.strip() for l in thinking.split("\n") if l.strip() and not l.startswith("*") and not l.startswith("#") and len(l.strip()) > 20]
            response = lines[-1] if lines else "Please continue."
    except Exception as e:
        response = "Sorry, please repeat that."
        print(f"Ollama error: {e}")

    print(f"RESPONSE: '{response[:80]}'")

    # Count exchanges — force report after 12 user messages
    user_msg_count = sum(1 for m in conversation if m["role"] == "user")
    
    # Force report generation if model didnt output JSON but said complete
    if user_msg_count >= 10 and "CLINICAL_REPORT:" not in response:
        force_prompt = f"""Based on this conversation, output ONLY a CLINICAL_REPORT JSON now. No other text.
Conversation summary: {json.dumps(conversation[-6:], ensure_ascii=False)}
Output format: CLINICAL_REPORT:{{"name":"","age":"","gender":"","complaint":"","duration":"","severity":"","associated":[],"history":"","medications":"","allergies":"","urgency":"LOW/MEDIUM/HIGH","department":"General Medicine","investigations":[],"summary":"clinical paragraph"}}"""
        try:
            force_r = requests.post(OLLAMA_URL, json={
                "model": FAST_MODEL,
                "messages": [{"role": "user", "content": force_prompt}],
                "stream": False,
                "keep_alive": -1,
                "think": False,
                "options": {"num_ctx": 2048, "temperature": 0.0, "num_predict": 400}
            }, timeout=180)
            force_response = force_r.json()["message"]["content"].strip()
            print(f"[FORCED REPORT]: {force_response[:200]}")
            if "CLINICAL_REPORT:" in force_response:
                response = force_response
        except Exception as e:
            print(f"Force report error: {e}")

    is_complete = "CLINICAL_REPORT:" in response
    clean_response = response

    if is_complete:
        try:
            json_str = response.split("CLINICAL_REPORT:")[1].strip()
            quick = json.loads(json_str)
            department = quick.get("department", "General Medicine")
            urgency = quick.get("urgency", "LOW")
            # Save department, name, age to DB
            conn_dept = get_db()
            conn_dept.execute(
                "UPDATE patients SET name=?, age=?, gender=?, department=?, status=?, updated_at=? WHERE token=?",
                (quick.get("name",""), quick.get("age",""), quick.get("gender",""),
                 department, "processing", datetime.now().isoformat(), token))
            conn_dept.commit()
            conn_dept.close()
            clean_response = get_department_message(department, token, language)
            
            # Broadcast to ESP32 bot via MQTT
            mqtt_payload = {
                "token": token,
                "name": quick.get("name", ""),
                "age": quick.get("age", ""),
                "department": department,
                "urgency": urgency,
                "action": "navigate",
                "malayalam": f"ടോക്കൺ {token}, {department} വിഭാഗത്തിലേക്ക് പോകൂ"
            }
            threading.Thread(target=lambda: mqtt_publish(MQTT_TOPIC_BOT, mqtt_payload), daemon=True).start()
            print(f"[REPORT] Quick JSON parsed OK: dept={quick.get('department')}, urgency={quick.get('urgency')}")
            print(f"[REPORT] Summary: {quick.get('summary','')[:100]}")
            conn.execute("UPDATE patients SET clinical_report=?, status=?, updated_at=? WHERE token=?",
                        (json.dumps(quick), "processing", datetime.now().isoformat(), token))
            conn.commit()
            threading.Thread(target=generate_full_report, args=(conversation, token), daemon=True).start()
        except Exception as e:
            print(f"Report parse: {e}")

    conversation.append({"role": "assistant", "content": clean_response})
    conn.execute("UPDATE patients SET conversation=?, updated_at=? WHERE token=?",
                (json.dumps(conversation), datetime.now().isoformat(), token))
    conn.commit()
    conn.close()

    return jsonify({"message": clean_response, "complete": is_complete, "token": token, "audio": None})

@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400
    f = request.files["audio"]
    language = request.form.get("language", "ml")
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        f.save(tmp.name)
        text, detected = transcribe_audio(tmp.name, language)
        os.unlink(tmp.name)
    return jsonify({"text": text, "language": detected})

@app.route("/api/queue")
def queue():
    conn = get_db()
    rows = conn.execute("SELECT token,name,age,gender,status,language,department,created_at,clinical_report FROM patients ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/patient/<token>")
def get_patient(token):
    conn = get_db()
    p = conn.execute("SELECT * FROM patients WHERE token=?", (token,)).fetchone()
    conn.close()
    return jsonify(dict(p)) if p else (jsonify({"error": "Not found"}), 404)

@app.route("/api/patient/<token>/update", methods=["POST"])
def update_patient(token):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE patients SET prescription=?,lab_orders=?,vitals=?,status=?,updated_at=? WHERE token=?",
                (d.get("prescription",""), d.get("lab_orders",""),
                 json.dumps(d.get("vitals",{})), d.get("status","with_doctor"),
                 datetime.now().isoformat(), token))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/bot/next/<token>")
def bot_next_destination(token):
    """ESP32 robot calls this to get where to guide the patient next."""
    conn = get_db()
    p = conn.execute("SELECT token,name,department,status,vitals FROM patients WHERE token=?", (token,)).fetchone()
    conn.close()
    if not p:
        return jsonify({"error": "Not found"}), 404
    p = dict(p)
    
    # Map status to physical location
    location_map = {
        "processing": {"location": "waiting_area", "display": "Please wait in the waiting area"},
        "ready": {"location": p["department"].lower().replace(" ","_"), "display": f"Please proceed to {p['department']}"},
        "with_doctor": {"location": "doctor_room", "display": "Doctor is ready for you"},
        "done": {"location": "pharmacy_or_lab", "display": "Proceed to pharmacy or lab as instructed"}
    }
    dest = location_map.get(p["status"], {"location": "waiting_area", "display": "Please wait"})
    
    return jsonify({
        "token": p["token"],
        "name": p["name"],
        "department": p["department"],
        "status": p["status"],
        "next_location": dest["location"],
        "display_message": dest["display"],
        "malayalam_message": {
            "waiting_area": "ദയവായി കാത്തിരിക്കൂ",
            "doctor_room": "ഡോക്ടർ നിങ്ങളെ കാണാൻ തയ്യാറാണ്",
            "pharmacy_or_lab": "ഫാർമസി അല്ലെങ്കിൽ ലാബിലേക്ക് പോകൂ"
        }.get(dest["location"], "ദയവായി കാത്തിരിക്കൂ")
    })


if __name__ == "__main__":
    init_db()
    print("Database ready")
    print("RAG loaded")
    print("Kiosk:  http://192.168.11.245:5000/")
    print("Doctor: http://192.168.11.245:5000/doctor")
    threading.Thread(target=warmup, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
