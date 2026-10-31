"""
Dostana - "Your friend in the digital world"   (ALL-IN-ONE FILE)

Is ek file mein DONO cheezein hain:
  1. Website (Flask): Bank, Chat, Post Office, The Gate, 6 stories, Translate, Read aloud
  2. Hamesha screen par rehne wala "Madad" button: dabane par screen parh kar sawal hal karta hai

Install:   pip install flask openai pillow mss PyQt6 pyttsx3
API key:   set OPENROUTER_API_KEY=sk-or-v1-...   (Windows)
Run:       python mera_mohalla.py
           (browser khud khulta hai; Madad button screen ke neeche-right mein aata hai)

NOTE: "Madad" dabane par screenshot OpenRouter ke zariye selected vision model ko bheja jata hai.
"""
import os
import re
import sqlite3
from datetime import datetime

from flask import (Flask, g, request, redirect, url_for, jsonify,
                   render_template, flash)
from jinja2 import DictLoader
from markupsafe import Markup, escape

import sys
import io
import base64
import threading
import webbrowser
import json
import urllib.request
import urllib.error

from openai import OpenAI
from PIL import Image
import mss

from PyQt6.QtWidgets import (QApplication, QLabel, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint, QRect, QRectF, QPointF
from PyQt6.QtGui import QFont, QGuiApplication, QPainter, QColor, QPen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mohalla.db")

app = Flask(__name__)
app.secret_key = "change-this-secret"
USER_NAME = "Janab"          # <-- yahan naam badlein


# ======================================================================
# 1. BILINGUAL HELPER  (English + Roman Urdu)
# ======================================================================
def T(en, ur):
    """Renders English and a hidden Roman Urdu line (shown by Translate)."""
    return Markup(f'<span class="en">{escape(en)}</span>'
                  f'<span class="ur">{escape(ur)}</span>')


app.jinja_env.globals["T"] = T


# ======================================================================
# 2. CONTENT DATA  (yahan se content badlein)
# ======================================================================
PLACES = [
    dict(icon="🏛️", url="bank", name=("Bank", "Bank"),
         desc=("Send or check money", "Paisay bhejein ya check karein")),
    dict(icon="💬", url="chat", name=("Chat with family", "Family se baat karein"),
         desc=("WhatsApp messages and calls", "WhatsApp messages aur calls")),
    dict(icon="✉️", url="post", name=("Post Office", "Dakghar"),
         desc=("Read your emails and letters", "Apni emails aur khat parhein")),
    dict(icon="🛡️", url="gate", name=("The Gate", "Darwaza"),
         desc=("Check if a message is a trick", "Check karein ke message dhoka to nahi")),
]

SC = {
    "door": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><rect x="40" y="8" width="38" height="64" rx="4"/><circle cx="68" cy="42" r="2.5" fill="#f3c9a6"/><circle cx="135" cy="26" r="13"/><path d="M118 26h34" stroke="#e0707a"/><path d="M112 72c0-16 10-24 23-24s23 8 23 24" stroke="#e0707a"/></svg>',
    "call": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M40 14h16l7 18-9 6a40 40 0 0 0 18 18l6-9 18 7v16a6 6 0 0 1-6 6C58 76 30 48 34 20a6 6 0 0 1 6-6z" transform="scale(.8) translate(4 -2)"/><path d="M112 72V30l30-16 30 16v42M105 72h74M128 72V52h28v20" stroke="#e0707a"/></svg>',
    "sms": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><rect x="38" y="8" width="44" height="64" rx="8"/><path d="M52 62h16"/><rect x="118" y="30" width="46" height="34" rx="3" stroke="#e0707a"/><path d="M118 36l23 15 23-15M141 30v-8M133 26l8-8 8 8" stroke="#e0707a"/></svg>',
    "help": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M88 14H44a8 8 0 0 0-8 8v26a8 8 0 0 0 8 8h8v12l14-12h22a8 8 0 0 0 8-8V22a8 8 0 0 0-8-8z"/><path d="M62 30h18M62 42h12"/><path d="M148 20l10 20h-20z M148 52v2" stroke="#e0707a"/></svg>',
    "parcel": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M40 28l32-16 32 16v34L72 78 40 62z" transform="translate(0 -4) scale(.9)"/><path d="M40 28l32 16 32-16M72 44v34" transform="translate(0 -4) scale(.9)"/><circle cx="148" cy="40" r="20" stroke="#e0707a"/><path d="M148 30v20M141 34h11a4 4 0 0 1 0 8h-8a4 4 0 0 0 0 8h11" stroke="#e0707a" transform="scale(.9) translate(16 4)"/></svg>',
    "remote": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><rect x="30" y="10" width="64" height="44" rx="4"/><path d="M52 70h20M62 54v16"/><circle cx="148" cy="40" r="22" stroke="#e0707a"/><path d="M134 40h28M148 26v28" stroke="#e0707a" stroke-width="2"/></svg>',
    "done": '<svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="100" cy="40" r="26"/><path d="M88 41l9 9 16-18" stroke="#e0707a"/></svg>'
}

STORIES = [
    dict(id=1, scene=SC["door"],
         title=("A stranger is at your door", "Ek ajnabi darwaze par hai"),
         text=('He says: "Congratulations! You won a prize. Tell me the code on your phone."',
               'Woh kehta hai: "Mubarak ho, inaam nikla hai! Apne phone ka code bata dein."'),
         choices=[(("Tell him the code", "Usay code bata dein"), False),
                  (("Do NOT tell him", "Usay code mat batayein"), True)],
         good=("Correct! Never share a code from your phone with anyone.",
               "Bilkul theek! Phone ka code kisi ko na batayein."),
         bad=("No! That code can empty your bank account.",
              "Nahi! Is code se aap ka account khali ho sakta hai.")),
    dict(id=2, scene=SC["call"],
         title=("A call from 'the bank'", "'Bank' se phone aaya"),
         text=('A voice says: "Your account will be blocked today. Tell me the OTP we just sent."',
               'Awaaz kehti hai: "Aap ka account aaj band ho jayega. Abhi bheja gaya OTP bata dein."'),
         choices=[(("Read out the OTP", "OTP parh kar suna dein"), False),
                  (("Hang up and call the bank myself", "Phone band karein, bank ko khud call karein"), True)],
         good=("Correct! Real banks never ask for your OTP.",
               "Bilkul theek! Asli bank kabhi OTP nahi poochta."),
         bad=("No! Whoever asks for the OTP is a thief.",
              "Nahi! OTP mangne wala chor hota hai.")),
    dict(id=3, scene=SC["sms"],
         title=("A prize message with a link", "Inaam ka message aur link"),
         text=('SMS: "You won Rs 500,000! Click this link to collect your prize."',
               'SMS: "Aap ne 5 lakh rupay jeete! Inaam lene ke liye link dabayein."'),
         choices=[(("Click the link", "Link dabayein"), False),
                  (("Delete it, do not click", "Delete kar dein, link na dabayein"), True)],
         good=("Correct! Prize links steal your money and data.",
               "Bilkul theek! Inaam ke link paisay aur data chura lete hain."),
         bad=("No! Clicking can install bad software on your phone.",
              "Nahi! Link dabane se phone mein kharab software aa sakta hai.")),
    dict(id=4, scene=SC["help"],
         title=("'Your grandson' needs money", "'Aap ka pota' paisay mang raha hai"),
         text=('WhatsApp from a new number: "Dadu, I lost my phone. Send Rs 20,000 now, please."',
               'Naye number se WhatsApp: "Dadu, mera phone kho gaya. Abhi 20,000 bhej dein."'),
         choices=[(("Send the money fast", "Foran paisay bhej dein"), False),
                  (("Call my family on the old number", "Purane number par family ko call karein"), True)],
         good=("Correct! Always check with a call before sending money.",
               "Bilkul theek! Paisay bhejne se pehle call kar ke tasdeeq karein."),
         bad=("No! This is a common trick. Call first.",
              "Nahi! Yeh aam dhoka hai. Pehle call karein.")),
    dict(id=5, scene=SC["parcel"],
         title=("A parcel needs a fee", "Parcel ki fees maangi ja rahi hai"),
         text=('Message: "Your parcel is stuck. Pay Rs 150 at this link to receive it."',
               'Message: "Aap ka parcel ruka hai. Wasool karne ke liye is link par 150 rupay dein."'),
         choices=[(("Pay at the link", "Link par paisay dein"), False),
                  (("Ignore it, I ordered nothing", "Nazar andaaz karein, maine kuch mangwaya nahi"), True)],
         good=("Correct! Small fees are used to steal card details.",
               "Bilkul theek! Choti fees se card ki maloomat chori hoti hain."),
         bad=("No! They want your card number.",
              "Nahi! Woh aap ka card number chahte hain.")),
    dict(id=6, scene=SC["remote"],
         title=("'Helper' wants to fix your phone", "'Madadgar' phone theek karna chahta hai"),
         text=('A caller says: "Install this app so I can fix your phone from here."',
               'Caller kehta hai: "Yeh app install karein, main door se phone theek kar doon ga."'),
         choices=[(("Install the app", "App install kar lein"), False),
                  (("Refuse and tell my family", "Mana karein aur family ko batayein"), True)],
         good=("Correct! Such apps let thieves see your whole phone.",
               "Bilkul theek! Aise app se chor poora phone dekh lete hain."),
         bad=("No! They could see your bank app and passwords.",
              "Nahi! Woh bank app aur passwords dekh sakte hain.")),
]
STORY_BY_ID = {s["id"]: s for s in STORIES}

LETTERS = [
    dict(frm="Easypaisa Support", scam=True,
         subject=("Account blocked! Verify now", "Account band! Abhi tasdeeq karein"),
         body=("Dear user, send your CNIC and PIN to keep your account open.",
               "Pyare sarif, account chalu rakhne ke liye CNIC aur PIN bhejein."),
         why=("Real companies never ask for your PIN.", "Asli companies PIN kabhi nahi mangti.")),
    dict(frm="Beta (your son)", scam=False,
         subject=("Dinner on Sunday", "Itwaar ko khana"),
         body=("Abba, we will come on Sunday for dinner. Love, Ahmed.",
               "Abba, hum itwaar ko khane par aayenge. Ahmed."),
         why=("This is from family, with no money or code asked.",
              "Yeh family ki taraf se hai, paisay ya code nahi manga.")),
    dict(frm="PTCL-Offers", scam=True,
         subject=("You won a free mobile!", "Aap ne free mobile jeeta!"),
         body=("Click http://free-gift.example to claim. Offer ends in 2 hours!",
               "Lene ke liye link dabayein. Offer 2 ghante mein khatam!"),
         why=("A link, a prize and a rush: three signs of a trick.",
              "Link, inaam aur jaldi: dhoke ki teen nishaniyan.")),
    dict(frm="Dr. Saleem's Clinic", scam=False,
         subject=("Appointment reminder", "Appointment ki yaad dehani"),
         body=("Your check-up is on Tuesday 5 pm. Please bring old reports.",
               "Aap ka check-up mangal ko 5 baje hai. Purani reports le aayein."),
         why=("It only gives information and asks for nothing.",
              "Sirf maloomat hai, kuch mangta nahi.")),
]

# ---- Scam checker rules for "The Gate": (regex, points, reason) ----
RULES = [
    (r"\b(otp|code|pin|password|cvv)\b", 3,
     ("It asks for a secret code or PIN.", "Yeh khufia code ya PIN mangta hai.")),
    (r"https?://|www\.|bit\.ly|tinyurl", 2,
     ("It has a link.", "Is mein link hai.")),
    (r"\b(urgent|immediately|last chance|blocked|suspended|expire[sd]?|within \d+ (hours?|minutes?))\b|abhi|foran", 2,
     ("It rushes you.", "Yeh aap ko jaldi mein daalta hai.")),
    (r"\b(won|winner|prize|lottery|congratulations|free gift)\b|inaam|jeet", 3,
     ("It promises a prize.", "Yeh inaam ka wada karta hai.")),
    (r"\b(send money|transfer|easypaisa|jazzcash|pay|fee|charges)\b|paisay", 2,
     ("It asks for money.", "Yeh paisay mangta hai.")),
    (r"\b(anydesk|teamviewer|install|apk|download)\b", 3,
     ("It wants you to install an app.", "Yeh app install karwana chahta hai.")),
    (r"\b(cnic|account number|card number)\b", 2,
     ("It asks for personal details.", "Yeh zaati maloomat mangta hai.")),
]


def check_message(text):
    score, reasons = 0, []
    for pattern, pts, reason in RULES:
        if re.search(pattern, text, re.I):
            score += pts
            reasons.append(reason)
    if score >= 5:
        verdict = ("danger", ("DANGER: This is a trick. Do not reply or click.",
                              "KHATRA: Yeh dhoka hai. Jawab na dein, link na dabayein."))
    elif score >= 2:
        verdict = ("caution", ("Be careful. Ask your family before doing anything.",
                               "Ehtiyat karein. Kuch karne se pehle family se poochein."))
    else:
        verdict = ("ok", ("Nothing suspicious found, but still ask if unsure.",
                          "Koi shak wali cheez nahi mili, phir bhi shak ho to poochein."))
    return score, verdict, reasons


# ======================================================================
# 3. DATABASE (SQLite)
# ======================================================================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS progress(story_id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS safety_unlocks(
            story_id INTEGER PRIMARY KEY, unlocked_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, number TEXT);
        CREATE TABLE IF NOT EXISTS tx(
            id INTEGER PRIMARY KEY AUTOINCREMENT, who TEXT, amount INTEGER, ts TEXT);
    """)
    db.execute("INSERT OR IGNORE INTO settings VALUES('balance','50000')")
    if db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0:
        db.execute("INSERT INTO contacts(name, number) VALUES('Ahmed (son)', '923001234567')")
        db.execute("INSERT INTO contacts(name, number) VALUES('Sana (daughter)', '923011234567')")
    db.commit()
    db.close()


def get_balance():
    row = get_db().execute("SELECT value FROM settings WHERE key='balance'").fetchone()
    return int(row["value"])


def finished_ids():
    rows = get_db().execute("SELECT story_id FROM progress").fetchall()
    return {r["story_id"] for r in rows}


@app.context_processor
def inject_globals():
    db = get_db()
    first = db.execute("SELECT number FROM contacts ORDER BY id LIMIT 1").fetchone()
    done = len(finished_ids())
    return dict(user_name=USER_NAME, done=done, total=len(STORIES),
                family_number=first["number"] if first else None)


# ======================================================================
# 4. ROUTES
# ======================================================================
@app.route("/")
def home():
    done = finished_ids()
    # A safety story unlocked by Madad takes priority over the normal six-story sequence.
    unlocked = get_db().execute(
        "SELECT story_id FROM safety_unlocks ORDER BY unlocked_at DESC LIMIT 1"
    ).fetchone()
    story = STORY_BY_ID.get(unlocked["story_id"]) if unlocked else None
    if story and story["id"] in done:
        story = None
    if story is None:
        story = next((s for s in STORIES if s["id"] not in done), None)
    return render_template("home.html", places=PLACES, story=story)


# ---- Story answer (called from JS) ----
@app.route("/api/story/<int:sid>/answer", methods=["POST"])
def story_answer(sid):
    story = STORY_BY_ID.get(sid)
    if not story:
        return jsonify(error="not found"), 404
    idx = int((request.get_json(silent=True) or {}).get("choice", -1))
    if not 0 <= idx < len(story["choices"]):
        return jsonify(error="bad choice"), 400
    correct = story["choices"][idx][1]
    if correct:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO progress VALUES(?)", (sid,))
        db.execute("DELETE FROM safety_unlocks WHERE story_id=?", (sid,))
        db.commit()
    msg = story["good"] if correct else story["bad"]
    return jsonify(correct=correct, en=msg[0], ur=msg[1],
                   done=len(finished_ids()), total=len(STORIES))


# ---- Madad can unlock a matching safety lesson on the home page ----
@app.route("/api/safety/unlock", methods=["POST"])
def safety_unlock():
    # Flask is bound to 127.0.0.1 only; this endpoint is for the local desktop helper.
    payload = request.get_json(silent=True) or {}
    try:
        sid = int(payload.get("story_id", 0))
    except (TypeError, ValueError):
        sid = 0
    if sid not in STORY_BY_ID:
        return jsonify(ok=False, error="unknown story"), 400
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO safety_unlocks(story_id, unlocked_at) VALUES(?, ?)",
        (sid, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return jsonify(ok=True, story_id=sid)


# ---- Bank (practice money only) ----
@app.route("/bank", methods=["GET", "POST"])
def bank():
    db = get_db()
    contacts = db.execute("SELECT * FROM contacts ORDER BY id").fetchall()
    if request.method == "POST":
        who = request.form.get("who", "")
        other = request.form.get("other", "").strip()
        try:
            amount = int(request.form.get("amount", "0"))
        except ValueError:
            amount = 0
        if who == "other":
            if not other:
                flash(("error", "Please type who you want to pay.", "Likhein kis ko paisay dene hain."))
                return redirect(url_for("bank"))
            if not request.form.get("sure"):
                flash(("error", "Stop! You do not know this person. Tick the box only if you are sure, "
                                "or ask your family first.",
                       "Ruk jayein! Aap is shakhs ko nahi jante. Pakka yaqeen ho to dabba tick karein, "
                       "warna pehle family se poochein."))
                return redirect(url_for("bank"))
            who = other
        if amount <= 0:
            flash(("error", "Enter an amount more than zero.", "Sifar se zyada raqam likhein."))
        elif amount > get_balance():
            flash(("error", "You do not have enough money.", "Aap ke paas itne paisay nahi."))
        else:
            db.execute("UPDATE settings SET value=? WHERE key='balance'",
                       (str(get_balance() - amount),))
            db.execute("INSERT INTO tx(who, amount, ts) VALUES(?,?,?)",
                       (who, amount, datetime.now().strftime("%d %b %H:%M")))
            db.commit()
            flash(("ok", f"Sent Rs {amount} to {who}. (practice money)",
                   f"{who} ko Rs {amount} bhej diye. (mashq ke paisay)"))
        return redirect(url_for("bank"))
    txs = db.execute("SELECT * FROM tx ORDER BY id DESC LIMIT 8").fetchall()
    return render_template("bank.html", balance=get_balance(), contacts=contacts, txs=txs)


# ---- Chat with family ----
@app.route("/chat")
def chat():
    contacts = get_db().execute("SELECT * FROM contacts ORDER BY id").fetchall()
    return render_template("chat.html", contacts=contacts)


# ---- Post Office ----
@app.route("/post")
def post():
    return render_template("post.html", letters=LETTERS)


# ---- The Gate (scam checker) ----
@app.route("/gate", methods=["GET", "POST"])
def gate():
    result = None
    text = ""
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        if text:
            score, verdict, reasons = check_message(text)
            result = dict(score=score, level=verdict[0], verdict=verdict[1], reasons=reasons)
    return render_template("gate.html", result=result, text=text)


# ---- Settings (family numbers) ----
@app.route("/settings", methods=["GET", "POST"])
def settings():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            number = re.sub(r"\D", "", request.form.get("number", ""))
            if name and number:
                db.execute("INSERT INTO contacts(name, number) VALUES(?,?)", (name, number))
                db.commit()
                flash(("ok", "Family member added.", "Family ka fard shamil ho gaya."))
            else:
                flash(("error", "Type a name and a number.", "Naam aur number likhein."))
        elif action == "delete":
            db.execute("DELETE FROM contacts WHERE id=?", (request.form.get("id"),))
            db.commit()
        elif action == "reset":
            db.execute("DELETE FROM progress")
            db.commit()
            flash(("ok", "Stories restarted.", "Kahaniyan dobara shuru."))
        return redirect(url_for("settings"))
    contacts = db.execute("SELECT * FROM contacts ORDER BY id").fetchall()
    return render_template("settings.html", contacts=contacts)


# ======================================================================
# 5. TEMPLATES (HTML inside Python, so only ONE file is needed)
# ======================================================================
BASE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dostana</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@400;500;600;700;800&family=Noto+Nastaliq+Urdu:wght@500;700&display=swap" rel="stylesheet">
<style>
:root{--green:#8b1e2d;--cream:#faf3ec;--ink:#1c1c1a;--rust:#a35a00;--dark:#2a1518;--peach:#f3c9a6;--mint:#f7e4e4;--foot:#f0e4d8}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Urbanist","Segoe UI",system-ui,sans-serif;background:var(--cream);color:var(--ink);min-height:100vh;display:flex;flex-direction:column;font-size:22px;line-height:1.35}
a{color:inherit;text-decoration:none}
header{background:var(--green);color:#fff;padding:14px 28px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.brand h1{font-size:36px}.brand small{display:block;font-size:17px;opacity:.9}
.pill{background:transparent;color:#fff;border:3px solid #fff;border-radius:40px;padding:12px 22px;font-size:20px;font-weight:700;cursor:pointer}
.pill:hover{background:rgba(255,255,255,.15)}
.top-btns{display:flex;gap:10px;flex-wrap:wrap}
main{flex:1;padding:28px;max-width:1200px;width:100%;margin:0 auto}
.two{display:grid;grid-template-columns:1.6fr 1fr;gap:28px}
@media(max-width:900px){.two{grid-template-columns:1fr}}
h2{font-size:44px;margin-bottom:6px}.sub{font-size:24px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:560px){.grid{grid-template-columns:1fr}}
.card{background:#fff;border:2px solid #e6d3c6;box-shadow:0 4px 14px rgba(90,30,40,.10);border-radius:20px;padding:20px;display:flex;flex-direction:column;gap:14px}
.card .head{display:flex;gap:14px}
.icon{width:62px;height:62px;border-radius:14px;background:var(--mint);display:grid;place-items:center;font-size:32px;flex:none}
.card h3{font-size:30px;line-height:1.1;margin-bottom:6px}
.row{display:flex;gap:12px;margin-top:auto}
.btn{display:block;text-align:center;background:var(--green);color:#fff;border:none;border-radius:14px;padding:14px 18px;font-size:23px;font-weight:700;cursor:pointer;flex:1}
.btn.alt{background:#fff;color:var(--rust);border:3px solid var(--rust);padding:11px 14px;font-size:20px}
.ur{display:none;font-style:italic;color:var(--rust);font-size:.95em}
body.roman .ur,.show .ur{display:block}
aside{background:var(--dark);color:#fff;border-radius:24px;padding:24px;align-self:start}
aside .ur{color:var(--peach)}
aside .label{color:var(--peach);letter-spacing:2px;font-weight:700;font-size:17px;margin-bottom:12px}
.scene{background:#3d2327;border-radius:12px;height:100px;display:grid;place-items:center;font-size:54px;margin-bottom:14px}
aside h3{font-size:32px;margin-bottom:10px}aside p{margin-bottom:10px;font-size:23px}
.choice{display:block;width:100%;background:transparent;color:#fff;border:3px solid #fff;border-radius:14px;padding:14px;font-size:23px;font-weight:700;cursor:pointer;margin-top:12px;text-align:left}
.choice:hover{background:rgba(255,255,255,.12)}
.fb{margin-top:14px;padding:14px;border-radius:12px;display:none}
.fb.good{display:block;background:#2f6b4f}.fb.bad{display:block;background:#8c3b2a}
.fb .ur{color:#fff}
footer{background:var(--foot);border-top:2px solid #e6d3c6;padding:14px 28px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.progress{display:flex;align-items:center;gap:10px;font-weight:700;flex-wrap:wrap}
.box{width:36px;height:36px;border:3px solid var(--green);border-radius:8px;background:#fff;display:inline-block}
.box.done{background:var(--green)}
.family{background:#fff;border:3px solid var(--ink);border-radius:40px;padding:12px 26px;font-size:23px;font-weight:700}
.flash{max-width:1200px;margin:16px auto 0;padding:14px 20px;border-radius:12px;font-weight:600;width:calc(100% - 56px)}
.flash.ok{background:#cfe8da}.flash.error{background:#f5d3c9}
.panel{background:#fff;border:2px solid #e6d3c6;box-shadow:0 4px 14px rgba(90,30,40,.10);border-radius:20px;padding:24px;margin-bottom:20px}
label{display:block;font-weight:700;margin:12px 0 6px}
input[type=text],input[type=number],select,textarea{width:100%;padding:12px;font-size:22px;border:3px solid var(--ink);border-radius:12px;font-family:inherit}
textarea{min-height:140px}
.balance{font-size:52px;font-weight:800;color:var(--green)}
.warn{background:#fff3cd;border:3px solid #d9a400;border-radius:12px;padding:12px;margin-top:12px}
.result{border-radius:16px;padding:18px;margin-top:18px;border:3px solid var(--ink)}
.result.danger{background:#f5d3c9}.result.caution{background:#fff3cd}.result.ok{background:#cfe8da}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:2px solid #ddd;text-align:left}
.back{display:inline-block;margin-bottom:16px;font-weight:700;color:var(--green);font-size:22px}
.letter .why{display:none;margin-top:10px;padding:10px;border-radius:10px;background:var(--mint)}
.letter.answered .why{display:block}
.ic{width:1.1em;height:1.1em;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;vertical-align:-3px;margin-right:8px}
.icon svg{width:34px;height:34px;stroke:var(--green);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.btn.alt{display:flex;align-items:center;justify-content:center;white-space:nowrap}
.logo-ur{font-family:"Noto Nastaliq Urdu","Jameel Noori Nastaleeq",serif;font-size:32px;font-weight:700;line-height:1.9;display:inline-block;vertical-align:middle}
.brand h1{line-height:1.2}
</style></head>
<body>
<header>
  <a class="brand" href="{{ url_for('home') }}"><h1><svg class="ic" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6"/></svg><span class="logo-ur" lang="ur">دوستانہ</span></h1><small>Your friend in the digital world</small></a>
  <div class="top-btns">
    <button class="pill" id="transAll" type="button"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg>Translate all to Roman Urdu</button>
    <button class="pill" id="readAloud" type="button"><svg class="ic" viewBox="0 0 24 24"><path d="M3 9v6h4l5 4V5L7 9z"/><path d="M16 8a5 5 0 0 1 0 8M19 5a9 9 0 0 1 0 14"/></svg>Read aloud</button>
    <a class="pill" href="{{ url_for('settings') }}"><svg class="ic" style="margin:0" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9L7 7M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></svg></a>
  </div>
</header>
{% for m in get_flashed_messages() %}
  <div class="flash {{ m[0] }}">{{ T(m[1], m[2]) }}</div>
{% endfor %}
<main>{% block content %}{% endblock %}</main>
<footer>
  <div class="progress">
    <span>{{ T('Your Mohalla is growing:', 'Aap ka Mohalla barh raha hai:') }}</span>
    <span id="boxes">{% for i in range(total) %}<span class="box {{ 'done' if i < done }}"></span> {% endfor %}</span>
    <span id="count">{{ done }} of {{ total }} stories finished</span>
  </div>
  {% if family_number %}
  <a class="family" target="_blank" href="https://wa.me/{{ family_number }}"><svg class="ic" viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>Ask my family</a>
  {% else %}
  <a class="family" href="{{ url_for('settings') }}"><svg class="ic" viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>Add family number</a>
  {% endif %}
</footer>
<script>
const body = document.body, tBtn = document.getElementById('transAll');
const G='<svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg>';
function applyRoman(on){
  body.classList.toggle('roman', on);
  tBtn.innerHTML = G + (on ? 'Show English only' : 'Translate all to Roman Urdu');
  try{ localStorage.setItem('roman', on ? '1' : '0'); }catch(e){}
}
try{ applyRoman(localStorage.getItem('roman') === '1'); }catch(e){}
tBtn.onclick = () => applyRoman(!body.classList.contains('roman'));

document.getElementById('readAloud').onclick = () => {
  if(!('speechSynthesis' in window)){ alert('Your browser cannot read aloud.'); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(document.querySelector('main').innerText);
  u.rate = 0.85; speechSynthesis.speak(u);
};
function toggleShow(btn){ btn.closest('.card, .letter').classList.toggle('show'); }
</script>
{% block scripts %}{% endblock %}
</body></html>"""

HOME = """{% extends 'base.html' %}{% block content %}
{% set icons = {
'Bank':'<svg viewBox="0 0 24 24"><path d="M3 21h18M5 21V10M9 21V10M15 21V10M19 21V10M3 10l9-6 9 6"/></svg>',
'Chat with family':'<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
'Post Office':'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>',
'The Gate':'<svg viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/></svg>'
} %}
<div class="two">
  <section>
    <h2>Hello, {{ user_name }}.</h2>
    <p class="sub">{{ T('Where would you like to go today?', 'Aaj aap kahan jana chahenge?') }}</p>
    <div class="grid">
    {% for p in places %}
      <div class="card">
        <div class="head"><div class="icon">{{ icons.get(p.name[0], p.icon)|safe }}</div>
          <div><h3>{{ T(*p.name) }}</h3><p>{{ T(*p.desc) }}</p></div></div>
        <div class="row">
          <a class="btn" href="{{ url_for(p.url) }}">Go</a>
          <button class="btn alt" type="button" onclick="toggleShow(this)"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg>Translate</button>
        </div>
      </div>
    {% endfor %}
    </div>
  </section>
  <aside>
    <div class="label">TODAY'S STORY</div>
    {% if story %}
      <div class="scene">{{ story.scene|safe }}</div>
      <h3>{{ T(*story.title) }}</h3>
      <p>{{ T(*story.text) }}</p>
      {% for c in story.choices %}
        <button class="choice" type="button" onclick="answer({{ story.id }}, {{ loop.index0 }})">{{ T(*c[0]) }}</button>
      {% endfor %}
      <div class="fb" id="fb"></div>
      <a class="choice" id="next" href="{{ url_for('home') }}" style="display:none;text-align:center">Next story &rarr;</a>
    {% else %}
      <div class="scene"><svg viewBox="0 0 200 80" height="80" fill="none" stroke="#f3c9a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="100" cy="40" r="26"/><path d="M88 41l9 9 16-18" stroke="#e0707a"/></svg></div>
      <h3>{{ T('All stories finished!', 'Saari kahaniyan mukammal!') }}</h3>
      <p>{{ T('Well done. You can spot a trick now.', 'Shabash. Ab aap dhoka pehchan sakte hain.') }}</p>
    {% endif %}
  </aside>
</div>
{% endblock %}
{% block scripts %}{% if story %}<script>
async function answer(id, idx){
  const r = await fetch('/api/story/' + id + '/answer', {method:'POST',
     headers:{'Content-Type':'application/json'}, body: JSON.stringify({choice: idx})});
  const d = await r.json();
  const fb = document.getElementById('fb');
  fb.className = 'fb ' + (d.correct ? 'good' : 'bad');
  fb.innerHTML = '';
  const en = document.createElement('span'); en.className = 'en'; en.innerHTML = (d.correct ? '<svg class="ic" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>' : '<svg class="ic" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>'); en.append(document.createTextNode(d.en));
  const ur = document.createElement('span'); ur.className = 'ur'; ur.textContent = d.ur;
  fb.append(en, ur);
  if(d.correct){
    document.getElementById('next').style.display = 'block';
    document.getElementById('count').textContent = d.done + ' of ' + d.total + ' stories finished';
    document.querySelectorAll('#boxes .box').forEach((b, i) => b.classList.toggle('done', i < d.done));
  }
}
</script>{% endif %}{% endblock %}"""

BANK = """{% extends 'base.html' %}{% block content %}
<a class="back" href="{{ url_for('home') }}">&larr; Back</a>
<h2>{{ T('Bank', 'Bank') }}</h2>
<div class="warn">{{ T('Practice bank: this is not real money. Learn safely here.',
  'Mashq ka bank: yeh asli paisay nahi. Yahan mehfooz tareeqe se seekhein.') }}</div>
<div class="panel" style="margin-top:18px">
  <p>{{ T('Your balance', 'Aap ka balance') }}</p>
  <div class="balance">Rs {{ '{:,}'.format(balance) }}</div>
</div>
<div class="panel">
  <h3>{{ T('Send money', 'Paisay bhejein') }}</h3>
  <form method="post">
    <label>{{ T('Send to', 'Kis ko bhejna hai') }}</label>
    <select name="who" id="who" onchange="document.getElementById('otherBox').style.display = this.value==='other' ? 'block':'none'">
      {% for c in contacts %}<option value="{{ c.name }}">{{ c.name }}</option>{% endfor %}
      <option value="other">{{ 'Someone else / Kisi aur ko' }}</option>
    </select>
    <div id="otherBox" style="display:none">
      <label>{{ T('Name or number', 'Naam ya number') }}</label>
      <input type="text" name="other">
      <div class="warn"><label style="margin:0;font-weight:600"><input type="checkbox" name="sure" style="width:auto">
        {{ T('I know this person for sure.', 'Main is shakhs ko achi tarah jaanta hoon.') }}</label></div>
    </div>
    <label>{{ T('Amount (Rs)', 'Raqam (Rs)') }}</label>
    <input type="number" name="amount" min="1">
    <div class="row" style="margin-top:16px"><button class="btn" type="submit">{{ T('Send', 'Bhejein') }}</button></div>
  </form>
</div>
<div class="panel">
  <h3>{{ T('Recent payments', 'Haliya adaigiyan') }}</h3>
  {% if txs %}<table>{% for t in txs %}<tr><td>{{ t.ts }}</td><td>{{ t.who }}</td><td>Rs {{ t.amount }}</td></tr>{% endfor %}</table>
  {% else %}<p>{{ T('No payments yet.', 'Abhi koi adaigi nahi.') }}</p>{% endif %}
</div>
{% endblock %}"""

CHAT = """{% extends 'base.html' %}{% block content %}
<a class="back" href="{{ url_for('home') }}">&larr; Back</a>
<h2>{{ T('Chat with family', 'Family se baat karein') }}</h2>
<p class="sub">{{ T('Tap a name to open WhatsApp or make a call.', 'WhatsApp kholne ya call karne ke liye naam dabayein.') }}</p>
{% for c in contacts %}
<div class="panel" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
  <div><h3>{{ c.name }}</h3><p>+{{ c.number }}</p></div>
  <div class="row" style="margin:0">
    <a class="btn" target="_blank" href="https://wa.me/{{ c.number }}">WhatsApp</a>
    <a class="btn alt" href="tel:+{{ c.number }}"><svg class="ic" viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>Call</a>
  </div>
</div>
{% else %}
<div class="panel">{{ T('No family added yet.', 'Abhi koi family ka fard shamil nahi.') }}
  <a class="back" href="{{ url_for('settings') }}">Add / Shamil karein</a></div>
{% endfor %}
<div class="panel"><h3>{{ T('Safety tip', 'Hifazat ka mashwara') }}</h3>
<p>{{ T('If a message from a new number asks for money, call your family on their old number first.',
  'Naye number se paisay ka message aaye to pehle family ko purane number par call karein.') }}</p></div>
{% endblock %}"""

POST = """{% extends 'base.html' %}{% block content %}
<a class="back" href="{{ url_for('home') }}">&larr; Back</a>
<h2>{{ T('Post Office', 'Dakghar') }}</h2>
<p class="sub">{{ T('Read each letter. Is it real or a trick?', 'Har khat parhein. Asli hai ya dhoka?') }}</p>
{% for l in letters %}
<div class="panel letter" data-scam="{{ 1 if l.scam else 0 }}">
  <p><b>{{ l.frm }}</b></p>
  <h3>{{ T(*l.subject) }}</h3>
  <p>{{ T(*l.body) }}</p>
  <div class="row" style="margin-top:14px">
    <button class="btn" type="button" onclick="judge(this, 0)"><svg class="ic" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>{{ T('Real', 'Asli') }}</button>
    <button class="btn" style="background:var(--rust)" type="button" onclick="judge(this, 1)"><svg class="ic" viewBox="0 0 24 24"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/></svg>{{ T('Trick', 'Dhoka') }}</button>
  </div>
  <div class="why"><b class="verdict"></b><br>{{ T(*l.why) }}</div>
</div>
{% endfor %}
{% endblock %}
{% block scripts %}<script>
function judge(btn, guessScam){
  const card = btn.closest('.letter');
  const isScam = card.dataset.scam === '1';
  card.classList.add('answered');
  card.querySelector('.verdict').innerHTML =
     ((guessScam === (isScam ? 1 : 0)) ? '<svg class="ic" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>Correct! ' : '<svg class="ic" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>Not quite. ') +
     (isScam ? 'This is a trick (Yeh dhoka hai).' : 'This is real (Yeh asli hai).');
}
</script>{% endblock %}"""

GATE = """{% extends 'base.html' %}{% block content %}
<a class="back" href="{{ url_for('home') }}">&larr; Back</a>
<h2>{{ T('The Gate', 'Darwaza') }}</h2>
<p class="sub">{{ T('Paste a message you got. We will tell you if it looks like a trick.',
  'Jo message aaya hai yahan paste karein. Hum batayenge ke dhoka lagta hai ya nahi.') }}</p>
<div class="panel">
  <form method="post">
    <label>{{ T('Message', 'Message') }}</label>
    <textarea name="text" required>{{ text }}</textarea>
    <div class="row" style="margin-top:14px"><button class="btn" type="submit">{{ T('Check it', 'Check karein') }}</button></div>
  </form>
  {% if result %}
  <div class="result {{ result.level }}">
    <h3>{{ T(*result.verdict) }}</h3>
    {% if result.reasons %}<ul style="margin:10px 0 0 22px">
      {% for r in result.reasons %}<li>{{ T(*r) }}</li>{% endfor %}</ul>{% endif %}
  </div>
  {% endif %}
</div>
{% endblock %}"""

SETTINGS = """{% extends 'base.html' %}{% block content %}
<a class="back" href="{{ url_for('home') }}">&larr; Back</a>
<h2>{{ T('Family numbers', 'Family ke number') }}</h2>
<div class="panel">
  {% for c in contacts %}
  <form method="post" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:2px solid #ddd">
    <span>{{ c.name }} (+{{ c.number }})</span>
    <input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="{{ c.id }}">
    <button class="btn alt" style="flex:none" type="submit">Delete</button>
  </form>
  {% endfor %}
  <form method="post">
    <input type="hidden" name="action" value="add">
    <label>{{ T('Name', 'Naam') }}</label><input type="text" name="name">
    <label>{{ T('Number with country code (e.g. 923001234567)', 'Country code ke sath number (jaise 923001234567)') }}</label>
    <input type="text" name="number">
    <div class="row" style="margin-top:14px"><button class="btn" type="submit">{{ T('Add', 'Shamil karein') }}</button></div>
  </form>
</div>
<div class="panel">
  <form method="post"><input type="hidden" name="action" value="reset">
  <button class="btn alt" type="submit">{{ T('Restart all stories', 'Saari kahaniyan dobara shuru') }}</button></form>
</div>
{% endblock %}"""

app.jinja_loader = DictLoader({
    "base.html": BASE, "home.html": HOME, "bank.html": BANK, "chat.html": CHAT,
    "post.html": POST, "gate.html": GATE, "settings.html": SETTINGS,
})

# ======================================================================


# ======================================================================
# 5b. DESKTOP HELPER: hamesha screen par rehne wala "Madad" button
# ======================================================================
# ---------- Optional pieces (app in ke baghair bhi chalta hai) ----------
try:
    import pyttsx3
    HAS_TTS = True
except Exception:
    HAS_TTS = False

try:  # sirf hover-explain ke liye (Windows)
    import pytesseract
    import pywinauto
    from pywinauto.win32functions import GetCursorPos
    HAS_HOVER_LIBS = True
except Exception:
    HAS_HOVER_LIBS = False

# ======================================================================
# SETTINGS  (yahan se badlein)
# ======================================================================
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
FAMILY_NUMBER = "923001234567"      # sirf tab use hota hai jab settings mein koi family number na ho
ENABLE_HOVER_EXPLAIN = False        # True = mouse ke neeche wala text bhi samjhaye (har 1 sec API call)
BUTTON_SIZE = 96

# OpenRouter uses the OpenAI-compatible API. Never put your key directly in this file.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is not set. Set it in your environment before starting Dostana."
    )

openrouter_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

def safety_story_for_text(text: str):
    """Map risky words seen by Madad to one of the existing six lessons."""
    value = (text or "").lower()
    # More specific patterns come first so a parcel fee maps to its own lesson.
    if re.search(r"\b(parcel|delivery|courier|customs fee|shipping fee)\b", value):
        return 5
    if re.search(r"\b(anydesk|teamviewer|remote access|screen sharing|install this app|apk)\b", value):
        return 6
    if re.search(r"\b(otp|one[- ]time password|verification code|security code)\b", value):
        return 2
    if re.search(r"\b(pin|password|passcode|cvv|card number|bank code)\b", value):
        return 1
    if re.search(r"\b(prize|winner|lottery|won money|free gift|claim your reward|click this link)\b", value):
        return 3
    if re.search(r"\b(send money|transfer money|urgent payment|new number|lost my phone|easypaisa|jazzcash)\b", value):
        return 4
    return None


def notify_safety_story_unlock(text: str):
    """Ask the local Flask app to surface the matching lesson; never block Madad."""
    story_id = safety_story_for_text(text)
    if not story_id:
        return None
    try:
        body = json.dumps({"story_id": story_id}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/safety/unlock", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=1.5) as response:
            if response.status == 200:
                return story_id
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    return None


SCREEN_PROMPT = (
    "You are a calm, kind helper for an older adult who is not comfortable with phones and computers. "
    "You are given a screenshot of their screen. Work out what question, problem, form, error or "
    "message is on the screen, and solve it or answer it for them.\n"
    "Rules:\n"
    "- Use very simple words and a short household comparison if it helps. Max 5 short sentences.\n"
    "- If the task needs steps, give at most 4 numbered steps naming the exact button to press.\n"
    "- If the screen looks like a scam (prize, OTP/PIN/password request, urgent threat, unknown link, "
    "someone asking for money or to install an app), start with 'WARNING:' and clearly say do NOT "
    "click, pay or share anything, and call family.\n"
    "- Never ask the person to type passwords, PINs or OTPs into anything.\n"
    "- If you cannot tell what they need, say what you can see and ask them to tell their family.\n"
    "After the English answer, add a new line that starts with 'ROMAN URDU:' followed by the same "
    "answer written in Roman Urdu (Urdu in English letters)."
)


# ======================================================================
# SCREEN CAPTURE + OPENROUTER
# ======================================================================
def capture_screen_b64() -> str:
    """Primary monitor ka screenshot -> base64 JPEG (chhota kar ke)."""
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    img.thumbnail((1568, 1568))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def ask_openrouter_about_screen(b64_jpeg: str) -> tuple[str, str]:
    """Send the screenshot to a vision model through OpenRouter."""
    resp = openrouter_client.chat.completions.create(
        model=MODEL,
        max_tokens=600,
        messages=[
            {"role": "system", "content": SCREEN_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_jpeg}"}},
                    {"type": "text", "text": "Please help me with what is on my screen."},
                ],
            },
        ],
    )
    answer = (resp.choices[0].message.content or "").strip()
    unlocked_story_id = notify_safety_story_unlock(answer)
    if "ROMAN URDU:" in answer:
        en, ur = answer.split("ROMAN URDU:", 1)
    else:
        en, ur = answer, answer
    if unlocked_story_id:
        en += "\n\nI unlocked a matching safety story on the Dostana home page."
        ur += "\n\nMaine Dostana ke home page par is khatre se mutaliq kahani khol di hai."
    return en.strip(), ur.strip()


class Worker(QObject):
    """Background thread se Qt ko safely jawab bhejta hai."""
    answered = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def run(self, b64):
        try:
            en, ur = ask_openrouter_about_screen(b64)
            self.answered.emit(en, ur)
        except Exception as e:
            self.failed.emit(str(e))


# ======================================================================
# FLOATING BUTTON  (hamesha upar, drag bhi ho sakta hai)
# ======================================================================
class FloatingButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # screen ke neeche-right kone mein rakhein
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - BUTTON_SIZE - 30, geo.bottom() - BUTTON_SIZE - 30)

        self._press_pos = None
        self._drag_offset = QPoint()
        self._moved = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setBrush(QColor("#8B1E2D"))
        p.setPen(QPen(QColor("#FACC15"), 4))
        p.drawEllipse(QRectF(2, 2, w - 4, h - 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("white"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = w / 2
        p.drawEllipse(QPointF(cx - 3, 34), 9, 9)                 # magnifier lens
        p.drawLine(QPointF(cx + 4, 41), QPointF(cx + 12, 49))    # handle
        p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        p.drawText(QRect(0, 54, w, 28), Qt.AlignmentFlag.AlignCenter, "Madad")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._press_pos is not None:
            cur = e.globalPosition().toPoint()
            if (cur - self._press_pos).manhattanLength() > 6:
                self._moved = True
            if self._moved:
                self.move(cur - self._drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if not self._moved:          # drag nahi tha => click tha
                self.clicked.emit()
            self._press_pos = None


# ======================================================================
# ANSWER CARD
# ======================================================================
class AnswerCard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(480)
        self.english = ""
        self.roman = ""
        self.showing_roman = False

        outer = QVBoxLayout(self)
        self.frame = QWidget()
        self.frame.setStyleSheet("""
            QWidget#frame { background-color: #0F172A; border: 3px solid #FACC15; border-radius: 14px; }
        """)
        self.frame.setObjectName("frame")
        inner = QVBoxLayout(self.frame)

        self.text = QLabel("")
        self.text.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.text.setWordWrap(True)
        self.text.setStyleSheet("color: #FAF3EC; padding: 8px;")
        inner.addWidget(self.text)

        row = QHBoxLayout()
        self.btn_read = self._btn("Sunayen")
        self.btn_lang = self._btn("Roman Urdu")
        self.btn_family = self._btn("Family")
        self.btn_close = self._btn("Band")
        self.btn_read.clicked.connect(self.read_aloud)
        self.btn_lang.clicked.connect(self.toggle_lang)
        self.btn_family.clicked.connect(lambda: webbrowser.open(f"https://wa.me/{family_number_from_db()}"))
        self.btn_close.clicked.connect(self.hide)
        for b in (self.btn_read, self.btn_lang, self.btn_family, self.btn_close):
            row.addWidget(b)
        if not HAS_TTS:
            self.btn_read.hide()
        inner.addLayout(row)
        outer.addWidget(self.frame)
        self.hide()

    @staticmethod
    def _btn(label):
        b = QPushButton(label)
        b.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("""
            QPushButton { background:#8B1E2D; color:white; border:2px solid #FACC15;
                          border-radius:10px; padding:8px 10px; }
            QPushButton:hover { background:#A82A3C; }
        """)
        return b

    def show_message(self, msg, near: QWidget):
        self.text.setText(msg)
        self._set_buttons_enabled(False)
        self._place_near(near)
        self.show()
        self.adjustSize()
        self._place_near(near)

    def show_answer(self, en, ur, near: QWidget):
        self.english, self.roman = en, ur
        self.showing_roman = False
        self.btn_lang.setText("Roman Urdu")
        self.text.setText(en)
        self._set_buttons_enabled(True)
        self.show()
        self.adjustSize()
        self._place_near(near)

    def _set_buttons_enabled(self, on):
        for b in (self.btn_read, self.btn_lang):
            b.setEnabled(on)

    def toggle_lang(self):
        self.showing_roman = not self.showing_roman
        self.text.setText(self.roman if self.showing_roman else self.english)
        self.btn_lang.setText("English" if self.showing_roman else "Roman Urdu")
        self.adjustSize()

    def read_aloud(self):
        if not HAS_TTS:
            return
        text = self.text.text()

        def speak():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 150)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"TTS error: {e}")
        threading.Thread(target=speak, daemon=True).start()

    def _place_near(self, widget: QWidget):
        """Card ko button ke upar rakhein, screen ke andar rakhte hue."""
        geo = QGuiApplication.primaryScreen().availableGeometry()
        bw = widget.frameGeometry()
        x = min(max(geo.left() + 10, bw.right() - self.width()), geo.right() - self.width() - 10)
        y = bw.top() - self.height() - 12
        if y < geo.top() + 10:
            y = bw.bottom() + 12
        self.move(x, y)


# ======================================================================
# CONTROLLER: button click -> screenshot -> OpenRouter -> card
# ======================================================================
class Controller:
    def __init__(self):
        self.button = FloatingButton()
        self.card = AnswerCard()
        self.worker = Worker()
        self.busy = False
        self.button.clicked.connect(self.on_click)
        self.worker.answered.connect(self.on_answer)
        self.worker.failed.connect(self.on_fail)
        self.button.show()

    def on_click(self):
        if self.busy:
            return
        self.busy = True
        # Button aur card screenshot mein na aayein, isliye pehle chhupayein
        self.button.hide()
        self.card.hide()
        QTimer.singleShot(350, self._capture_and_ask)

    def _capture_and_ask(self):
        try:
            b64 = capture_screen_b64()
        except Exception as e:
            self.button.show()
            self.on_fail(f"Screen capture nahi hui: {e}")
            return
        self.button.show()
        self.card.show_message("Aap ki screen parh raha hoon...\nZara intezar karein.", self.button)
        threading.Thread(target=self.worker.run, args=(b64,), daemon=True).start()

    def on_answer(self, en, ur):
        self.busy = False
        self.card.show_answer(en, ur, self.button)

    def on_fail(self, err):
        self.busy = False
        print("Error:", err)
        self.card.show_message("Maaf kijiye, abhi screen parhi nahi ja saki.\nInternet ya API key check karein.",
                               self.button)
        self.card._set_buttons_enabled(False)


# ======================================================================
# OPTIONAL: aap ka purana hover-explain feature (ENABLE_HOVER_EXPLAIN=True par chalta hai)
# ======================================================================
class HybridTextExtractor:
    """Extracts text using UI Automation first, falling back to OCR if needed."""

    @staticmethod
    def get_text_at_cursor() -> tuple[str, str]:
        pt = GetCursorPos()
        x, y = pt.x, pt.y
        try:
            elem = pywinauto.uia_element_info.UIAElementInfo.from_point(x, y)
            uia_text = (elem.name or elem.rich_text or "").strip()
            if len(uia_text) > 3:
                return uia_text, "UI Automation (Direct)"
        except Exception:
            pass
        try:
            box_width, box_height = 300, 150
            left = max(0, x - (box_width // 2))
            top = max(0, y - (box_height // 2))
            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": box_width, "height": box_height}
                sct_img = sct.grab(monitor)
                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                ocr_text = pytesseract.image_to_string(pil_img).strip()
                if len(ocr_text) > 2:
                    return ocr_text, "OCR Fallback"
        except Exception as e:
            print(f"OCR Error: {e}")
        return "", "None"


class SeniorHybridOverlay(QWidget):
    """Floating card jo mouse ke neeche wala text saada alfaaz mein samjhata hai."""
    explained = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.last_text = ""
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout()
        self.label = QLabel("Hover over any text or button to explain...")
        self.label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.label.setStyleSheet("""
            background-color: #0F172A; color: #FACC15; border: 3px solid #FACC15;
            border-radius: 12px; padding: 16px; max-width: 380px;
        """)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.explained.connect(self.label.setText)
        self.hide()

    def process_hover(self):
        pt = GetCursorPos()
        text, method = HybridTextExtractor.get_text_at_cursor()
        if text and text != self.last_text:
            self.last_text = text
            self.move(pt.x + 25, pt.y + 25)
            self.label.setText(f"Reading ({method})...")
            self.show()
            threading.Thread(target=self._explain_with_openrouter, args=(text,), daemon=True).start()

    def _explain_with_openrouter(self, raw_text: str):
        try:
            response = openrouter_client.chat.completions.create(
                model=MODEL,
                max_tokens=150,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a reassuring assistant for older adults.\\n"
                            "Explain the provided technical text, error message, or button using a simple "
                            "household analogy.\\nKeep your response strictly under 2 short sentences."
                        ),
                    },
                    {"role": "user", "content": f"Simplify this screen text: {raw_text}"},
                ],
            )
            self.explained.emit(response.choices[0].message.content or "")
        except Exception:
            self.explained.emit("Could not translate this section right now.")


# ======================================================================


def family_number_from_db() -> str:
    """Settings (website) mein jo pehla family number hai wohi Madad card mein use hota hai."""
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute("SELECT number FROM contacts ORDER BY id LIMIT 1").fetchone()
        con.close()
        if row:
            return row[0]
    except Exception:
        pass
    return FAMILY_NUMBER


# ======================================================================
# 6. START EVERYTHING
# ======================================================================
def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()               # website
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    qt_app = QApplication(sys.argv)                                        # Madad button
    qt_app.setQuitOnLastWindowClosed(False)
    controller = Controller()

    hover_overlay = None
    if ENABLE_HOVER_EXPLAIN:
        if HAS_HOVER_LIBS:
            hover_overlay = SeniorHybridOverlay()
            hover_timer = QTimer()
            hover_timer.timeout.connect(hover_overlay.process_hover)
            hover_timer.start(1000)
        else:
            print("Hover feature ke liye: pip install pywinauto pytesseract (aur Tesseract OCR)")

    sys.exit(qt_app.exec())