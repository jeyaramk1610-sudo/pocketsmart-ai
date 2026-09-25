
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = DATA_DIR / "pocketsmart.db"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key-in-production")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# Small local recommendation catalog. The AI layer can enrich these when Gemini is configured.
HOME_CATALOG = [
    {"style": "Modern", "summary": "Clean lines, neutral tones, layered lighting, and practical storage.", "budget": "Budget-friendly"},
    {"style": "Minimal", "summary": "Simple furniture, uncluttered surfaces, soft colours, and open visual space.", "budget": "Budget-friendly"},
    {"style": "Traditional", "summary": "Warm wood, classic patterns, balanced décor, and a welcoming family feel.", "budget": "Mid-range"},
    {"style": "Luxury", "summary": "Statement lighting, rich textures, premium finishes, and elegant focal pieces.", "budget": "Premium"},
]

PARTY_CATALOG = [
    {"theme": "Elegant", "summary": "Simple coordinated décor, warm lighting, neat table styling, and a premium feel."},
    {"theme": "Birthday Fun", "summary": "Bright balloons, a photo corner, cake table styling, and simple games."},
    {"theme": "Family Celebration", "summary": "Comfortable seating, easy food service, group-photo space, and flexible décor."},
    {"theme": "Classic Traditional", "summary": "Traditional colours, floral décor, coordinated serving area, and family-friendly setup."},
]

JEWELRY_CATALOG = [
    {"type": "Classic", "summary": "A balanced, timeless jewellery direction that works across many occasions."},
    {"type": "Lightweight", "summary": "Simple pieces designed for comfort and an understated look."},
    {"type": "Statement", "summary": "One prominent piece with simpler supporting jewellery."},
    {"type": "Traditional", "summary": "Traditional-inspired shapes and coordinated pieces for cultural occasions."},
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            planner_type TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as conn:
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def save_recommendation(planner_type, inputs, result):
    user = current_user()
    if not user:
        return None
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO recommendations
            (user_id, planner_type, inputs_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                planner_type,
                json.dumps(inputs, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                now_iso(),
            ),
        )
        return cur.lastrowid


def keyword_score(text, keywords):
    text = (text or "").lower()
    return sum(1 for k in keywords if k in text)


def choose_home(style, room, budget):
    text = f"{style} {room} {budget}".lower()
    if "luxury" in text or "premium" in text:
        pick = HOME_CATALOG[3]
    elif "traditional" in text or "classic" in text:
        pick = HOME_CATALOG[2]
    elif "minimal" in text or "simple" in text:
        pick = HOME_CATALOG[1]
    else:
        pick = HOME_CATALOG[0]

    extras = []
    if budget:
        extras.append(f"Keep the main purchases within the {budget.lower()} range.")
    if room:
        extras.append(f"Prioritise storage and movement space for the {room.lower()}.")
    extras.extend([
        "Use 2–3 main materials or colours so the room feels coordinated.",
        "Add one focal element such as a feature wall, rug, artwork, or statement light.",
        "Plan lighting in layers: general, task, and accent lighting."
    ])

    return {
        "title": f"{pick['style']} {room or 'Room'} Plan",
        "summary": pick["summary"],
        "suggestions": extras,
        "estimated_budget_note": pick["budget"],
    }


def choose_party(theme, guests, budget, occasion):
    text = f"{theme} {occasion} {budget}".lower()
    if "birthday" in text:
        pick = PARTY_CATALOG[1]
    elif "traditional" in text or "classic" in text:
        pick = PARTY_CATALOG[3]
    elif "family" in text:
        pick = PARTY_CATALOG[2]
    else:
        pick = PARTY_CATALOG[0]

    guest_count = int(guests or 0)
    space_note = "Arrange flexible seating and a clear photo area."
    if guest_count >= 50:
        space_note = "Use zones for food, seating, photos, and movement so the crowd flows smoothly."
    elif guest_count >= 25:
        space_note = "Create separate food and seating areas and leave a clear walkway."

    suggestions = [
        pick["summary"],
        space_note,
        "Reserve part of the budget for food/drinks, then décor and contingency.",
        "Use one main backdrop or photo corner rather than decorating every surface.",
    ]
    if budget:
        suggestions.append(f"Target the total setup around your {budget.lower()} budget.")

    return {
        "title": f"{pick['theme']} Party Plan",
        "summary": f"Designed for {occasion or 'your event'} with about {guest_count or 'your'} guests.",
        "suggestions": suggestions,
    }


def choose_jewelry(occasion, outfit, budget):
    text = f"{occasion} {outfit} {budget}".lower()
    if "wedding" in text or "bridal" in text:
        pick = JEWELRY_CATALOG[3]
    elif "party" in text or "reception" in text:
        pick = JEWELRY_CATALOG[2]
    elif "office" in text or "college" in text:
        pick = JEWELRY_CATALOG[1]
    else:
        pick = JEWELRY_CATALOG[0]

    suggestions = [
        pick["summary"],
        f"Coordinate the jewellery with the {outfit or 'outfit'} colour family.",
        "Keep one hero piece and make the supporting pieces simpler.",
    ]
    if budget:
        suggestions.append(f"Stay within the {budget.lower()} range by prioritising the hero piece.")

    return {
        "title": f"{pick['type']} Jewellery Plan",
        "summary": f"Suggested for {occasion or 'your occasion'}.",
        "suggestions": suggestions,
        "selected_type": pick["type"],
    }


def gemini_generate(prompt):
    """
    Optional Gemini REST integration.
    The app still works without an API key and uses its built-in recommendation engine.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    if not api_key:
        return None

    try:
        import requests
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        response = requests.post(
            endpoint,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
    except Exception:
        return None


def maybe_enrich(planner_type, inputs, result):
    prompt = f"""
You are the recommendation engine for PocketSmart AI.
Planner type: {planner_type}
Inputs: {json.dumps(inputs, ensure_ascii=False)}
Base recommendation: {json.dumps(result, ensure_ascii=False)}

Improve the recommendation with practical, concise ideas. Do not invent prices or claim exact product availability.
Return plain text with a short heading and 4-6 useful suggestions.
"""
    ai_text = gemini_generate(prompt)
    if ai_text:
        result["ai_note"] = ai_text.strip()
        result["ai_enabled"] = True
    else:
        result["ai_enabled"] = False
    return result


@app.route("/")
def index():
    return render_template("index.html", user=current_user())


@app.route("/register")
def register_page():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login")
def login_page():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    return render_template("dashboard.html", user=user)


@app.route("/planner/<planner_type>")
def planner_page(planner_type):
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    if planner_type not in {"home", "party", "jewelry"}:
        return redirect(url_for("dashboard"))
    return render_template("planner.html", planner_type=planner_type, user=user)


@app.route("/history")
def history_page():
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    return render_template("history.html", user=user)


@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or len(password) < 6:
        return jsonify({"ok": False, "message": "Enter your name, a valid email, and a password of at least 6 characters."}), 400

    try:
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), now_iso()),
            )
            session["user_id"] = cur.lastrowid
        return jsonify({"ok": True, "message": "Registration successful."})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "message": "That email is already registered."}), 409


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    with db() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"ok": False, "message": "Invalid email or password."}), 401

    session["user_id"] = row["id"]
    return jsonify({"ok": True, "message": "Login successful."})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/session")
def api_session():
    user = current_user()
    return jsonify({"ok": True, "authenticated": bool(user), "user": user})


@app.post("/api/planner/home")
def api_home():
    if not current_user():
        return jsonify({"ok": False, "message": "Please log in first."}), 401
    data = request.get_json(silent=True) or {}
    inputs = {
        "room": (data.get("room") or "").strip(),
        "style": (data.get("style") or "").strip(),
        "budget": (data.get("budget") or "").strip(),
    }
    result = choose_home(**inputs)
    result = maybe_enrich("home", inputs, result)
    rec_id = save_recommendation("home", inputs, result)
    result["recommendation_id"] = rec_id
    return jsonify({"ok": True, "result": result})


@app.post("/api/planner/party")
def api_party():
    if not current_user():
        return jsonify({"ok": False, "message": "Please log in first."}), 401
    data = request.get_json(silent=True) or {}
    inputs = {
        "theme": (data.get("theme") or "").strip(),
        "guests": (data.get("guests") or "").strip(),
        "budget": (data.get("budget") or "").strip(),
        "occasion": (data.get("occasion") or "").strip(),
    }
    result = choose_party(**inputs)
    result = maybe_enrich("party", inputs, result)
    rec_id = save_recommendation("party", inputs, result)
    result["recommendation_id"] = rec_id
    return jsonify({"ok": True, "result": result})


@app.post("/api/planner/jewelry")
def api_jewelry():
    if not current_user():
        return jsonify({"ok": False, "message": "Please log in first."}), 401

    inputs = {
        "occasion": (request.form.get("occasion") or "").strip(),
        "outfit": (request.form.get("outfit") or "").strip(),
        "budget": (request.form.get("budget") or "").strip(),
    }

    uploaded = request.files.get("photo")
    saved_name = None
    if uploaded and uploaded.filename:
        ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"ok": False, "message": "Please upload a PNG, JPG, JPEG, or WEBP image."}), 400
        saved_name = f"{uuid.uuid4().hex}.{ext}"
        uploaded.save(UPLOAD_DIR / saved_name)
        inputs["photo_filename"] = saved_name

    result = choose_jewelry(**inputs)
    result = maybe_enrich("jewelry", inputs, result)
    rec_id = save_recommendation("jewelry", inputs, result)
    result["recommendation_id"] = rec_id
    return jsonify({"ok": True, "result": result})


@app.get("/api/history")
def api_history():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "message": "Please log in first."}), 401

    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, planner_type, inputs_json, result_json, created_at
            FROM recommendations
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user["id"],),
        ).fetchall()

    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "planner_type": row["planner_type"],
            "inputs": json.loads(row["inputs_json"]),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        })
    return jsonify({"ok": True, "items": items})


@app.get("/api/recommendation/<int:rec_id>")
def api_recommendation(rec_id):
    user = current_user()
    if not user:
        return jsonify({"ok": False, "message": "Please log in first."}), 401

    with db() as conn:
        row = conn.execute(
            """
            SELECT id, planner_type, inputs_json, result_json, created_at
            FROM recommendations
            WHERE id = ? AND user_id = ?
            """,
            (rec_id, user["id"]),
        ).fetchone()

    if not row:
        return jsonify({"ok": False, "message": "Recommendation not found."}), 404

    return jsonify({
        "ok": True,
        "item": {
            "id": row["id"],
            "planner_type": row["planner_type"],
            "inputs": json.loads(row["inputs_json"]),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }
    })


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    # Files are only used as optional planner input; direct access is intentionally limited to known upload names.
    safe = secure_filename(filename)
    target = UPLOAD_DIR / safe
    if target.exists() and target.is_file():
        from flask import send_from_directory
        return send_from_directory(UPLOAD_DIR, safe)
    return ("Not found", 404)


init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"\nPocketSmart AI running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
