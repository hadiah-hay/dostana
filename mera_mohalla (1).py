"""
Mera Mohalla - "Your phone, explained as a neighbourhood"   (ALL-IN-ONE FILE)

Is ek file mein DONO cheezein hain:
  1. Website (Flask): Bank, Chat, Post Office, The Gate, 6 stories, Translate, Read aloud
  2. Hamesha screen par rehne wala "Madad" button: dabane par screen parh kar sawal hal karta hai

Install:   pip install flask anthropic pillow mss PyQt6
           (awaaz ke liye kuch aur zaroori nahi: Windows ki apni awaaz use hoti hai. pyttsx3 optional hai)
API key:   pehli dafa app khud poochti hai aur api_key.txt mein save kar leti hai.
           Ya:  setx ANTHROPIC_API_KEY sk-ant-...   (phir naya terminal kholein; quotes na lagayein)
Run:       python mera_mohalla.py
           (browser khud khulta hai; Madad button screen ke neeche-right mein aata hai)
Check:     python mera_mohalla.py --test     <- API, screenshot aur awaaz teeno ko check karta hai

Madad button: click = poori screen parhe.  Right-click ya card ka "Screenshot" button =
  hissa chunein / clipboard se / tasveer file se (jab koi app screen parhne na de).

NOTE: Madad dabane par screenshot (ya clipboard ka text/tasveer) Anthropic API ko bheja jata hai.
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
import subprocess
import tempfile
import shutil

import anthropic
from anthropic import Anthropic
from PIL import Image, ImageStat
import mss
MSS = getattr(mss, "MSS", None) or mss.mss      # naye aur purane mss dono par chalta hai

from PyQt6.QtWidgets import (QApplication, QLabel, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QMenu, QFileDialog,
                             QInputDialog, QLineEdit)
from PyQt6.QtCore import (Qt, QTimer, pyqtSignal, pyqtSlot, QObject, QPoint,
                          QRect, QBuffer, QByteArray, QIODevice)
from PyQt6.QtGui import (QFont, QGuiApplication, QImage, QPainter, QColor,
                         QPen, QCursor)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mohalla.db")

app = Flask(__name__)
app.secret_key = "change-this-secret"
USER_NAME = "Abba Ji"          # <-- yahan naam badlein


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

STORIES = [
    dict(id=1, scene="🚪🕶️",
         title=("A stranger is at your door", "Ek ajnabi darwaze par hai"),
         text=('He says: "Congratulations! You won a prize. Tell me the code on your phone."',
               'Woh kehta hai: "Mubarak ho, inaam nikla hai! Apne phone ka code bata dein."'),
         choices=[(("Tell him the code", "Usay code bata dein"), False),
                  (("Do NOT tell him", "Usay code mat batayein"), True)],
         good=("Correct! Never share a code from your phone with anyone.",
               "Bilkul theek! Phone ka code kisi ko na batayein."),
         bad=("No! That code can empty your bank account.",
              "Nahi! Is code se aap ka account khali ho sakta hai.")),
    dict(id=2, scene="📞🏦",
         title=("A call from 'the bank'", "'Bank' se phone aaya"),
         text=('A voice says: "Your account will be blocked today. Tell me the OTP we just sent."',
               'Awaaz kehti hai: "Aap ka account aaj band ho jayega. Abhi bheja gaya OTP bata dein."'),
         choices=[(("Read out the OTP", "OTP parh kar suna dein"), False),
                  (("Hang up and call the bank myself", "Phone band karein, bank ko khud call karein"), True)],
         good=("Correct! Real banks never ask for your OTP.",
               "Bilkul theek! Asli bank kabhi OTP nahi poochta."),
         bad=("No! Whoever asks for the OTP is a thief.",
              "Nahi! OTP mangne wala chor hota hai.")),
    dict(id=3, scene="📱🎁",
         title=("A prize message with a link", "Inaam ka message aur link"),
         text=('SMS: "You won Rs 500,000! Click this link to collect your prize."',
               'SMS: "Aap ne 5 lakh rupay jeete! Inaam lene ke liye link dabayein."'),
         choices=[(("Click the link", "Link dabayein"), False),
                  (("Delete it, do not click", "Delete kar dein, link na dabayein"), True)],
         good=("Correct! Prize links steal your money and data.",
               "Bilkul theek! Inaam ke link paisay aur data chura lete hain."),
         bad=("No! Clicking can install bad software on your phone.",
              "Nahi! Link dabane se phone mein kharab software aa sakta hai.")),
    dict(id=4, scene="💬🆘",
         title=("'Your grandson' needs money", "'Aap ka pota' paisay mang raha hai"),
         text=('WhatsApp from a new number: "Dadu, I lost my phone. Send Rs 20,000 now, please."',
               'Naye number se WhatsApp: "Dadu, mera phone kho gaya. Abhi 20,000 bhej dein."'),
         choices=[(("Send the money fast", "Foran paisay bhej dein"), False),
                  (("Call my family on the old number", "Purane number par family ko call karein"), True)],
         good=("Correct! Always check with a call before sending money.",
               "Bilkul theek! Paisay bhejne se pehle call kar ke tasdeeq karein."),
         bad=("No! This is a common trick. Call first.",
              "Nahi! Yeh aam dhoka hai. Pehle call karein.")),
    dict(id=5, scene="📦💸",
         title=("A parcel needs a fee", "Parcel ki fees maangi ja rahi hai"),
         text=('Message: "Your parcel is stuck. Pay Rs 150 at this link to receive it."',
               'Message: "Aap ka parcel ruka hai. Wasool karne ke liye is link par 150 rupay dein."'),
         choices=[(("Pay at the link", "Link par paisay dein"), False),
                  (("Ignore it, I ordered nothing", "Nazar andaaz karein, maine kuch mangwaya nahi"), True)],
         good=("Correct! Small fees are used to steal card details.",
               "Bilkul theek! Choti fees se card ki maloomat chori hoti hain."),
         bad=("No! They want your card number.",
              "Nahi! Woh aap ka card number chahte hain.")),
    dict(id=6, scene="🖥️🛠️",
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
        db.commit()
    msg = story["good"] if correct else story["bad"]
    return jsonify(correct=correct, en=msg[0], ur=msg[1],
                   done=len(finished_ids()), total=len(STORIES))


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


# ---- Awaaz (computer ki apni awaaz; browser ki awaaz na chale to yeh kaam aati hai) ----
# JSON content-type zaroori hai, isliye doosri websites yahan se awaaz nahi chala sakteen (CORS preflight).
@app.route("/api/speak", methods=["POST"])
def api_speak():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()[:6000]
    if not text:
        return jsonify(ok=False, error="empty text"), 400
    ok, err = speaker.speak(text, wait=True)
    return jsonify(ok=ok, error=err)


@app.route("/api/stop", methods=["POST"])
def api_stop():
    speaker.stop()
    return jsonify(ok=True)



# ======================================================================
# 5. TEMPLATES (HTML inside Python, so only ONE file is needed)
# ======================================================================
BASE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mera Mohalla</title>
<style>
:root{--green:#1f5e4d;--cream:#f4efe2;--ink:#1c1c1a;--rust:#a8452a;--dark:#1f2a26;--peach:#f3c9a6;--mint:#e0eee8;--foot:#ede4d0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--cream);color:var(--ink);min-height:100vh;display:flex;flex-direction:column;font-size:18px}
a{color:inherit;text-decoration:none}
header{background:var(--green);color:#fff;padding:14px 28px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.brand h1{font-size:28px}.brand small{display:block;font-size:14px;opacity:.9}
.pill{background:transparent;color:#fff;border:3px solid #fff;border-radius:40px;padding:10px 20px;font-size:17px;font-weight:700;cursor:pointer}
.pill:hover{background:rgba(255,255,255,.15)}
.top-btns{display:flex;gap:10px;flex-wrap:wrap}
main{flex:1;padding:28px;max-width:1200px;width:100%;margin:0 auto}
.two{display:grid;grid-template-columns:1.6fr 1fr;gap:28px}
@media(max-width:900px){.two{grid-template-columns:1fr}}
h2{font-size:36px;margin-bottom:6px}.sub{font-size:20px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:560px){.grid{grid-template-columns:1fr}}
.card{background:#fff;border:3px solid var(--ink);border-radius:20px;padding:20px;display:flex;flex-direction:column;gap:14px}
.card .head{display:flex;gap:14px}
.icon{width:56px;height:56px;border-radius:14px;background:var(--mint);display:grid;place-items:center;font-size:28px;flex:none}
.card h3{font-size:25px;line-height:1.1;margin-bottom:6px}
.row{display:flex;gap:12px;margin-top:auto}
.btn{display:block;text-align:center;background:var(--green);color:#fff;border:none;border-radius:14px;padding:13px 18px;font-size:19px;font-weight:700;cursor:pointer;flex:1}
.btn.alt{background:#fff;color:var(--rust);border:3px solid var(--rust);padding:10px 14px;font-size:17px}
.ur{display:none;font-style:italic;color:var(--rust);font-size:.92em}
body.roman .ur,.show .ur{display:block}
aside{background:var(--dark);color:#fff;border-radius:24px;padding:24px;align-self:start}
aside .ur{color:var(--peach)}
aside .label{color:var(--peach);letter-spacing:2px;font-weight:700;font-size:14px;margin-bottom:12px}
.scene{background:#2d3d37;border-radius:12px;height:100px;display:grid;place-items:center;font-size:54px;margin-bottom:14px}
aside h3{font-size:27px;margin-bottom:10px}aside p{margin-bottom:10px;font-size:19px}
.choice{display:block;width:100%;background:transparent;color:#fff;border:3px solid #fff;border-radius:14px;padding:13px;font-size:19px;font-weight:700;cursor:pointer;margin-top:12px;text-align:left}
.choice:hover{background:rgba(255,255,255,.12)}
.fb{margin-top:14px;padding:14px;border-radius:12px;display:none}
.fb.good{display:block;background:#2f6b4f}.fb.bad{display:block;background:#8c3b2a}
.fb .ur{color:#fff}
footer{background:var(--foot);border-top:3px solid var(--ink);padding:14px 28px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.progress{display:flex;align-items:center;gap:10px;font-weight:700;flex-wrap:wrap}
.box{width:34px;height:34px;border:3px solid var(--green);border-radius:8px;background:#fff;display:inline-block}
.box.done{background:var(--green)}
.family{background:#fff;border:3px solid var(--ink);border-radius:40px;padding:11px 24px;font-size:19px;font-weight:700}
.flash{max-width:1200px;margin:16px auto 0;padding:14px 20px;border-radius:12px;font-weight:600;width:calc(100% - 56px)}
.flash.ok{background:#cfe8da}.flash.error{background:#f5d3c9}
.panel{background:#fff;border:3px solid var(--ink);border-radius:20px;padding:24px;margin-bottom:20px}
label{display:block;font-weight:700;margin:12px 0 6px}
input[type=text],input[type=number],select,textarea{width:100%;padding:12px;font-size:18px;border:3px solid var(--ink);border-radius:12px;font-family:inherit}
textarea{min-height:130px}
.balance{font-size:44px;font-weight:800;color:var(--green)}
.warn{background:#fff3cd;border:3px solid #d9a400;border-radius:12px;padding:12px;margin-top:12px}
.result{border-radius:16px;padding:18px;margin-top:18px;border:3px solid var(--ink)}
.result.danger{background:#f5d3c9}.result.caution{background:#fff3cd}.result.ok{background:#cfe8da}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:2px solid #ddd;text-align:left}
.back{display:inline-block;margin-bottom:16px;font-weight:700;color:var(--green)}
.letter .why{display:none;margin-top:10px;padding:10px;border-radius:10px;background:var(--mint)}
.letter.answered .why{display:block}
</style></head>
<body>
<header>
  <a class="brand" href="{{ url_for('home') }}"><h1>🏠 Mera Mohalla</h1><small>Your phone, explained as a neighbourhood</small></a>
  <div class="top-btns">
    <button class="pill" id="transAll" type="button">🌐 Translate all to Roman Urdu</button>
    <button class="pill" id="readAloud" type="button">🔊 Read aloud</button>
    <a class="pill" href="{{ url_for('settings') }}">⚙️</a>
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
  <a class="family" target="_blank" href="https://wa.me/{{ family_number }}">📞 Ask my family</a>
  {% else %}
  <a class="family" href="{{ url_for('settings') }}">📞 Add family number</a>
  {% endif %}
</footer>
<script>
const body = document.body, tBtn = document.getElementById('transAll');
function applyRoman(on){
  body.classList.toggle('roman', on);
  tBtn.textContent = on ? '🌐 Show English only' : '🌐 Translate all to Roman Urdu';
  try{ localStorage.setItem('roman', on ? '1' : '0'); }catch(e){}
}
try{ applyRoman(localStorage.getItem('roman') === '1'); }catch(e){}
tBtn.onclick = () => applyRoman(!body.classList.contains('roman'));

// ---- Read aloud: pehle browser ki awaaz, na chale to computer ki apni awaaz ----
const raBtn = document.getElementById('readAloud');
let reading = false, session = 0, keepAlive = [];
function setReading(on){ reading = on; raBtn.textContent = on ? '⏹ Stop reading' : '🔊 Read aloud'; }
function postJSON(url, obj){
  return fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(obj || {})});
}
function splitChunks(text){            // chhote tukde: Chrome lambi awaaz beech mein rok deta hai
  const out = [];
  text.split(String.fromCharCode(10)).forEach(line => {
    line = line.trim(); if(!line) return;
    let cur = '';
    (line.match(/[^.!?]+[.!?]*/g) || [line]).forEach(s => {
      if(cur && (cur + s).length > 160){ out.push(cur.trim()); cur = ''; }
      cur += s + ' ';
    });
    if(cur.trim()) out.push(cur.trim());
  });
  return out;
}
function stopReading(){
  session++;
  try{ speechSynthesis.cancel(); }catch(e){}
  postJSON('/api/stop').catch(() => {});
  setReading(false);
}
function speakWithComputer(text, my){
  setReading(true);
  postJSON('/api/speak', {text: text}).then(r => r.json()).then(d => {
    if(my !== session) return;
    setReading(false);
    if(!d.ok) alert('Sorry, the computer voice did not work: ' + (d.error || 'unknown error'));
  }).catch(() => { if(my === session) setReading(false); });
}
function speakWithBrowser(text, my){
  const chunks = splitChunks(text);
  const voices = speechSynthesis.getVoices();
  const voice = voices.find(v => /^en[-_](IN|PK|GB|US)/i.test(v.lang)) || voices.find(v => /^en/i.test(v.lang)) || voices[0];
  let started = false;
  keepAlive = [];
  setReading(true);
  const next = () => {
    if(my !== session) return;
    const part = chunks.shift();
    if(!part){ setReading(false); return; }
    const u = new SpeechSynthesisUtterance(part);
    if(voice){ u.voice = voice; u.lang = voice.lang; }
    u.rate = 0.85;
    u.onstart = () => { started = true; };
    u.onend = next;
    u.onerror = ev => {
      if(my !== session || ev.error === 'interrupted' || ev.error === 'canceled') return;
      speechSynthesis.cancel(); speakWithComputer(text, my);
    };
    keepAlive.push(u);                 // garbage-collect hone se bachane ke liye
    speechSynthesis.speak(u);
  };
  speechSynthesis.cancel();
  setTimeout(next, 150);               // cancel() ke foran baad speak() kabhi gum ho jata hai
  setTimeout(() => {                   // 3 second tak khamosh raha => computer ki awaaz
    if(my === session && !started){ speechSynthesis.cancel(); speakWithComputer(text, my); }
  }, 3000);
}
raBtn.onclick = () => {
  if(reading){ stopReading(); return; }
  const my = ++session;
  const text = document.querySelector('main').innerText.replace(/(\\p{Extended_Pictographic}|\\uFE0F)/gu, ' ');
  if(!('speechSynthesis' in window)){ speakWithComputer(text, my); return; }
  const go = () => speechSynthesis.getVoices().length ? speakWithBrowser(text, my) : speakWithComputer(text, my);
  if(speechSynthesis.getVoices().length){ go(); return; }
  let done = false;                    // awaazein der se load hoti hain
  const once = () => { if(!done){ done = true; go(); } };
  speechSynthesis.onvoiceschanged = once;
  setTimeout(once, 800);
};
function toggleShow(btn){ btn.closest('.card, .letter').classList.toggle('show'); }
</script>
{% block scripts %}{% endblock %}
</body></html>"""

HOME = """{% extends 'base.html' %}{% block content %}
<div class="two">
  <section>
    <h2>Hello, {{ user_name }}.</h2>
    <p class="sub">{{ T('Where would you like to go today?', 'Aaj aap kahan jana chahenge?') }}</p>
    <div class="grid">
    {% for p in places %}
      <div class="card">
        <div class="head"><div class="icon">{{ p.icon }}</div>
          <div><h3>{{ T(*p.name) }}</h3><p>{{ T(*p.desc) }}</p></div></div>
        <div class="row">
          <a class="btn" href="{{ url_for(p.url) }}">Go</a>
          <button class="btn alt" type="button" onclick="toggleShow(this)">🌐 Translate</button>
        </div>
      </div>
    {% endfor %}
    </div>
  </section>
  <aside>
    <div class="label">TODAY'S STORY</div>
    {% if story %}
      <div class="scene">{{ story.scene }}</div>
      <h3>{{ T(*story.title) }}</h3>
      <p>{{ T(*story.text) }}</p>
      {% for c in story.choices %}
        <button class="choice" type="button" onclick="answer({{ story.id }}, {{ loop.index0 }})">{{ T(*c[0]) }}</button>
      {% endfor %}
      <div class="fb" id="fb"></div>
      <a class="choice" id="next" href="{{ url_for('home') }}" style="display:none;text-align:center">Next story &rarr;</a>
    {% else %}
      <div class="scene">🎉</div>
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
  const en = document.createElement('span'); en.className = 'en'; en.textContent = (d.correct ? '✅ ' : '❌ ') + d.en;
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
<h2>🏛️ {{ T('Bank', 'Bank') }}</h2>
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
<h2>💬 {{ T('Chat with family', 'Family se baat karein') }}</h2>
<p class="sub">{{ T('Tap a name to open WhatsApp or make a call.', 'WhatsApp kholne ya call karne ke liye naam dabayein.') }}</p>
{% for c in contacts %}
<div class="panel" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
  <div><h3>{{ c.name }}</h3><p>+{{ c.number }}</p></div>
  <div class="row" style="margin:0">
    <a class="btn" target="_blank" href="https://wa.me/{{ c.number }}">WhatsApp</a>
    <a class="btn alt" href="tel:+{{ c.number }}">📞 Call</a>
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
<h2>✉️ {{ T('Post Office', 'Dakghar') }}</h2>
<p class="sub">{{ T('Read each letter. Is it real or a trick?', 'Har khat parhein. Asli hai ya dhoka?') }}</p>
{% for l in letters %}
<div class="panel letter" data-scam="{{ 1 if l.scam else 0 }}">
  <p><b>{{ l.frm }}</b></p>
  <h3>{{ T(*l.subject) }}</h3>
  <p>{{ T(*l.body) }}</p>
  <div class="row" style="margin-top:14px">
    <button class="btn" type="button" onclick="judge(this, 0)">✅ {{ T('Real', 'Asli') }}</button>
    <button class="btn" style="background:var(--rust)" type="button" onclick="judge(this, 1)">⚠️ {{ T('Trick', 'Dhoka') }}</button>
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
  card.querySelector('.verdict').textContent =
     ((guessScam === (isScam ? 1 : 0)) ? '✅ Correct! ' : '❌ Not quite. ') +
     (isScam ? 'This is a trick (Yeh dhoka hai).' : 'This is real (Yeh asli hai).');
}
</script>{% endblock %}"""

GATE = """{% extends 'base.html' %}{% block content %}
<a class="back" href="{{ url_for('home') }}">&larr; Back</a>
<h2>🛡️ {{ T('The Gate', 'Darwaza') }}</h2>
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
<h2>⚙️ {{ T('Family numbers', 'Family ke number') }}</h2>
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
MODEL = os.environ.get("MOHALLA_MODEL", "claude-sonnet-5-5")
FALLBACK_MODELS = ["claude-sonnet-4-6", "claude-haiku-5-5"]   # agar upar wala model na mile
FAMILY_NUMBER = "923001234567"      # sirf tab use hota hai jab settings mein koi family number na ho
ENABLE_HOVER_EXPLAIN = False        # True = mouse ke neeche wala text bhi samjhaye (har 1 sec API call)
BUTTON_SIZE = 96
SHOW_TECHNICAL_ERRORS = True        # True = card mein asal error bhi dikhta hai (masla dhoondne ke liye).
                                    # Jab sab theek chal jaye to Abba Ji ke liye False kar dein.
KEY_FILE = os.path.join(BASE_DIR, "api_key.txt")
ERROR_LOG = os.path.join(BASE_DIR, "mohalla_error.log")

anthropic_client = None             # init_client() se banta hai


# ======================================================================
# API KEY + CLIENT
# ======================================================================
class NoKeyError(Exception):
    pass


def clean_key(k):
    """Spaces, newline aur quotes hata deta hai (Windows: set KEY="sk-..." mein quotes key ka hissa ban jate hain)."""
    return (k or "").strip().strip('"').strip("'").strip()


def load_api_key():
    """Pehle api_key.txt, phir ANTHROPIC_API_KEY. Khali string = nahi mili."""
    try:
        with open(KEY_FILE, encoding="utf-8") as f:
            k = clean_key(f.read())
            if k:
                return k
    except OSError:
        pass
    k = clean_key(os.environ.get("ANTHROPIC_API_KEY"))
    return "" if k == "your-api-key-here" else k


def init_client(key):
    global anthropic_client
    anthropic_client = Anthropic(api_key=key, timeout=45.0, max_retries=1)


def ensure_api_key(force=False):
    """Key mil jaye to client banata hai, warna paste karne ko kehta hai. True = tayyar."""
    key = "" if force else load_api_key()
    if not key:
        text, ok = QInputDialog.getText(
            None, "Mera Mohalla - API key",
            "Apni Anthropic API key yahan paste karein (sk-ant-... se shuru hoti hai):",
            QLineEdit.EchoMode.Password)
        key = clean_key(text) if ok else ""
        if not key:
            return False
        try:
            with open(KEY_FILE, "w", encoding="utf-8") as f:
                f.write(key)
            try:
                os.chmod(KEY_FILE, 0o600)
            except Exception:
                pass
        except OSError as e:
            print("Key save nahi ho saki:", e)
    init_client(key)
    return True


def claude_call(**kwargs):
    """messages.create, aur agar model ka naam na mile to agla model aazmata hai."""
    if anthropic_client is None:
        raise NoKeyError("API key set nahi hai")
    last = None
    for m in [MODEL] + [x for x in FALLBACK_MODELS if x != MODEL]:
        try:
            return anthropic_client.messages.create(model=m, **kwargs)
        except anthropic.NotFoundError as e:
            last = e
            print(f"Model '{m}' nahi mila, agla aazma raha hoon...")
    raise last


def explain_error(e):
    """(kind, saada Roman Urdu paighaam)"""
    if isinstance(e, NoKeyError):
        return "key", "API key nahi mili.\n'Madad' dobara dabayein aur key paste karein."
    if isinstance(e, anthropic.AuthenticationError):
        return "key", ("API key theek nahi hai (ya expire ho gayi).\n"
                       "'Madad' dobara dabayein aur nayi key paste karein.")
    if isinstance(e, anthropic.PermissionDeniedError):
        return "perm", "Is key ya account ko ijazat nahi (403). Anthropic console mein account check karein."
    if isinstance(e, anthropic.RateLimitError):
        return "rate", "Bohat zyada requests ho gayin. Ek minute baad dobara koshish karein."
    if isinstance(e, anthropic.APITimeoutError):
        return "net", "Jawab aane mein bohat der lagi. Internet check kar ke dobara dabayein."
    if isinstance(e, anthropic.APIConnectionError):
        return "net", "Internet se connection nahi ban raha. Internet check karein."
    if isinstance(e, anthropic.NotFoundError):
        return "model", "Model ka naam nahi mila. Upar SETTINGS mein MODEL check karein."
    if isinstance(e, anthropic.BadRequestError):
        if "credit" in str(e).lower():
            return "credit", "Anthropic account mein credit khatam hai. console.anthropic.com > Billing dekhein."
        return "bad", "Request theek nahi gayi (400). Neeche detail dekhein."
    if isinstance(e, anthropic.APIStatusError) and getattr(e, "status_code", 0) >= 500:
        return "busy", "Anthropic ka server abhi masroof hai. Thori der baad dobara dabayein."
    return "other", "Maaf kijiye, abhi jawab nahi mil saka."


def log_error(e):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {type(e).__name__}: {e}"
    print("ERROR:", line)
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


SCREEN_PROMPT = (
    "You are a calm, kind helper for an older adult who is not comfortable with phones and computers. "
    "You are given a screenshot of their screen (or sometimes just text they copied from it). "
    "Work out what question, problem, form, error or message is on the screen, and solve it or answer it for them.\n"
    "Rules:\n"
    "- Use very simple words and a short household comparison if it helps. Max 5 short sentences.\n"
    "- If the task needs steps, give at most 4 numbered steps naming the exact button to press.\n"
    "- If the screen looks like a scam (prize, OTP/PIN/password request, urgent threat, unknown link, "
    "someone asking for money or to install an app), start with 'WARNING:' and clearly say do NOT "
    "click, pay or share anything, and call family.\n"
    "- Never ask the person to type passwords, PINs or OTPs into anything.\n"
    "- If a big part of the screenshot is plain black or empty where an app window should be, that app is "
    "probably blocking screenshots. Say so in one sentence and tell them to select the text, press Ctrl+C, "
    "and press the Screenshot button then Clipboard, or ask family.\n"
    "- If you cannot tell what they need, say what you can see and ask them to tell their family.\n"
    "After the English answer, add a new line that starts with 'ROMAN URDU:' followed by the same "
    "answer written in Roman Urdu (Urdu in English letters)."
)


def split_answer(text):
    text = text.replace("**", "").strip()
    m = re.search(r"(?i)\s*roman\s+urdu\s*:\s*", text)
    if m and text[:m.start()].strip():
        return text[:m.start()].strip(), text[m.end():].strip()
    return text, text


# ======================================================================
# SCREEN CAPTURE  (kayi tareeqe, kaali/khali screen pakadta hai)
# ======================================================================
def pil_to_qimage(img):
    img = img.convert("RGB")
    w, h = img.size
    data = img.tobytes("raw", "RGB")          # variable mein rakhein, warna memory chhin sakti hai
    return QImage(data, w, h, w * 3, QImage.Format.Format_RGB888).copy()


def qimage_to_pil(qimg):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    qimg.save(buf, "PNG")
    buf.close()
    return Image.open(io.BytesIO(bytes(ba))).convert("RGB")


def _grab_mss():
    with MSS() as sct:
        shot = sct.grab(sct.monitors[1])
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _grab_qt(screen):
    return qimage_to_pil(screen.grabWindow(0).toImage())


def _grab_pil():
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True).convert("RGB")


def looks_blank(img):
    """True agar tasveer poori kaali ya ek hi rang ki hai (app ne capture block kiya)."""
    small = img.convert("L").resize((96, 54))
    return ImageStat.Stat(small).stddev[0] < 2.0 or small.getextrema()[1] < 12


def grab_screen(near_point=None):
    """Returns (image, blank). Pehla theek tareeqa jeet'ta hai; sab kaali dein to blank=True."""
    methods = []
    have_qt = QGuiApplication.instance() is not None
    if have_qt:
        here = QGuiApplication.screenAt(near_point) if near_point is not None else None
        if here is not None and here != QGuiApplication.primaryScreen():
            methods.append(("Qt (is monitor ki)", lambda: _grab_qt(here)))
    methods.append(("mss", _grab_mss))
    if have_qt:
        methods.append(("Qt", lambda: _grab_qt(QGuiApplication.primaryScreen())))
    methods.append(("PIL", _grab_pil))

    first, errors = None, []
    for name, fn in methods:
        try:
            img = fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
        if not looks_blank(img):
            return img, False
        if first is None:
            first = img
    if first is not None:
        return first, True
    raise RuntimeError("Screenshot ka koi tareeqa kaam nahi kiya: " + " | ".join(errors))


def image_to_b64(img):
    img = img.convert("RGB")
    img.thumbnail((1568, 1568))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def ask_claude(img=None, text=None):
    """Returns (english, roman_urdu). img = PIL image, text = copy kiya hua text."""
    content = []
    if img is not None:
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": image_to_b64(img)}})
    if text:
        content.append({"type": "text", "text": "Text I copied from my screen:\n\n" + text[:6000]})
    content.append({"type": "text", "text": "Please help me with what is on my screen."})
    resp = claude_call(max_tokens=900, system=SCREEN_PROMPT,
                       messages=[{"role": "user", "content": content}])
    out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if not out:
        raise RuntimeError("Jawab khali aaya")
    return split_answer(out)


class Worker(QObject):
    """Background thread se Qt ko safely jawab bhejta hai."""
    answered = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)          # (kind, message)

    def run(self, img, text):
        try:
            en, ur = ask_claude(img, text)
            self.answered.emit(en, ur)
        except Exception as e:
            log_error(e)
            kind, msg = explain_error(e)
            if SHOW_TECHNICAL_ERRORS:
                msg += f"\n\n[{type(e).__name__}: {str(e)[:220]}]"
            self.failed.emit(kind, msg)


# ======================================================================
# AWAAZ  (Windows ki apni awaaz, pyttsx3 ke baghair bhi chalti hai)
# ======================================================================
PS_SPEAK = ("Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate = -1; $s.Volume = 100; "
            "$t = Get-Content -Raw -Encoding UTF8 -LiteralPath $env:MOHALLA_TEXT_FILE; "
            "$s.Speak($t)")


def clean_for_speech(text):
    text = re.sub(r"[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F\u200d]", "", text)   # emoji hata dein
    text = text.replace("*", "").replace("#", " ").replace("_", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


class Speaker:
    """Text ko awaaz mein sunata hai. Windows: PowerShell/SAPI, Mac: say, Linux: spd-say/espeak.
    Agar woh na chalein to pyttsx3 (agar installed ho)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._engine = None
        self._token = 0
        self.busy = False

    # ---- public ----
    def speak(self, text, on_done=None, wait=False):
        """Non-blocking (wait=False) ya blocking (wait=True). Returns (ok, error)."""
        self.stop()
        text = clean_for_speech(text)
        if not text:
            if on_done:
                on_done("")
            return True, ""
        with self._lock:
            self._token += 1
            tok = self._token
            self.busy = True

        def job():
            ok, err = self._speak_now(text, tok)
            with self._lock:
                current = (tok == self._token)
                if current:
                    self.busy = False
            if on_done and current:
                on_done("" if ok else err)
            return ok, err

        if wait:
            return job()
        threading.Thread(target=job, daemon=True).start()
        return True, ""

    def stop(self):
        with self._lock:
            self._token += 1
            self.busy = False
            proc, eng = self._proc, self._engine
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass

    # ---- internals ----
    def _speak_now(self, text, tok):
        if sys.platform.startswith("win"):
            methods = [self._win_powershell, self._pyttsx3]
        elif sys.platform == "darwin":
            methods = [lambda t, k: self._run_cmd(["say", "-r", "160", t], k), self._pyttsx3]
        else:
            methods = [self._linux_cmd, self._pyttsx3]
        errors = []
        for m in methods:
            if tok != self._token:
                return True, ""
            ok, err = m(text, tok)
            if tok != self._token or ok:
                return True, ""
            if err:
                errors.append(err)
        return False, " | ".join(errors) or "koi awaaz engine nahi mila"

    def _run_cmd(self, cmd, tok, env=None):
        flags = 0x08000000 if sys.platform.startswith("win") else 0      # CREATE_NO_WINDOW
        try:
            p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, creationflags=flags)
        except FileNotFoundError:
            return False, f"'{cmd[0]}' nahi mila"
        except Exception as e:
            return False, str(e)
        with self._lock:
            self._proc = p
            superseded = tok != self._token
        if superseded:
            p.terminate()
        _, err = p.communicate()
        if tok != self._token:
            return True, ""
        if p.returncode != 0:
            return False, (err or b"").decode(errors="ignore").strip()[:200] or f"exit code {p.returncode}"
        return True, ""

    def _win_powershell(self, text, tok):
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="mohalla_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            env = dict(os.environ, MOHALLA_TEXT_FILE=path)
            return self._run_cmd(["powershell", "-NoProfile", "-NonInteractive",
                                  "-ExecutionPolicy", "Bypass", "-Command", PS_SPEAK], tok, env)
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _linux_cmd(self, text, tok):
        for exe, args in (("spd-say", ["-w", "-r", "-20"]), ("espeak-ng", ["-s", "140"]), ("espeak", ["-s", "140"])):
            if shutil.which(exe):
                return self._run_cmd([exe] + args + [text], tok)
        return False, "spd-say / espeak installed nahi"

    def _pyttsx3(self, text, tok):
        if not HAS_TTS:
            return False, "pyttsx3 installed nahi"
        try:
            # Naye thread mein Windows COM chalu karna zaroori hai (yahi purana masla tha)
            for mod in ("comtypes", "pythoncom"):
                try:
                    __import__(mod).CoInitialize()
                    break
                except Exception:
                    pass
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            with self._lock:
                self._engine = engine
            engine.say(text)
            engine.runAndWait()
            return True, ""
        except Exception as e:
            return False, f"pyttsx3: {e}"


speaker = Speaker()


# ======================================================================
# FLOATING BUTTON  (hamesha upar, drag bhi ho sakta hai, right-click = menu)
# ======================================================================
class FloatingButton(QWidget):
    clicked = pyqtSignal()
    menu_requested = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)

        self.label = QLabel("🔍\nMadad", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.label.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.label.setStyleSheet(f"""
            background-color: #1F5E4D; color: white;
            border: 4px solid #FACC15; border-radius: {BUTTON_SIZE // 2}px;
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # screen ke neeche-right kone mein rakhein
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - BUTTON_SIZE - 30, geo.bottom() - BUTTON_SIZE - 30)

        self._press_pos = None
        self._drag_offset = QPoint()
        self._moved = False

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(e.globalPosition().toPoint())
            return
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
        if e.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            if not self._moved:          # drag nahi tha => click tha
                self.clicked.emit()
            self._press_pos = None


# ======================================================================
# SNIP OVERLAY  ("Screen ka hissa chunein")
# ======================================================================
class SnipOverlay(QWidget):
    """Screen par halka andhera; mouse se jo hissa chunein wahi Claude ko jata hai."""
    picked = pyqtSignal(object)        # PIL image
    cancelled = pyqtSignal()

    def __init__(self, pil_img, screen):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.pil = pil_img
        self.qimg = pil_to_qimage(pil_img)
        self.origin = None
        self.sel = QRect()
        self._finished = False
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def start(self):
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _scale(self):
        return self.pil.width / max(1, self.width()), self.pil.height / max(1, self.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(self.rect(), self.qimg)
        p.fillRect(self.rect(), QColor(0, 0, 0, 130))
        if not self.sel.isNull():
            r = self.sel.normalized()
            sx, sy = self.qimg.width() / max(1, self.width()), self.qimg.height() / max(1, self.height())
            p.drawImage(r, self.qimg, QRect(int(r.x() * sx), int(r.y() * sy),
                                            int(r.width() * sx), int(r.height() * sy)))
            p.setPen(QPen(QColor("#FACC15"), 3))
            p.drawRect(r)
        p.fillRect(QRect(0, 0, self.width(), 80), QColor(15, 23, 42, 235))
        p.setPen(QColor("#FACC15"))
        p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        p.drawText(QRect(0, 0, self.width(), 80), Qt.AlignmentFlag.AlignCenter,
                   "Jo hissa parhwana hai usay mouse se chunein   (Esc ya right-click = wapas)")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self._cancel()
        elif e.button() == Qt.MouseButton.LeftButton:
            self.origin = e.position().toPoint()
            self.sel = QRect(self.origin, self.origin)
            self.update()

    def mouseMoveEvent(self, e):
        if self.origin is not None:
            self.sel = QRect(self.origin, e.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self.origin is None:
            return
        r = self.sel.normalized()
        self.origin = None
        if r.width() < 25 or r.height() < 25:        # galti se click: dobara chunein
            self.sel = QRect()
            self.update()
            return
        sx, sy = self._scale()
        crop = self.pil.crop((int(r.left() * sx), int(r.top() * sy),
                              int(r.right() * sx), int(r.bottom() * sy)))
        self._finish(lambda: self.picked.emit(crop))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._cancel()

    def _cancel(self):
        self._finish(self.cancelled.emit)

    def _finish(self, emit):
        if self._finished:
            return
        self._finished = True
        self.close()
        emit()


# ======================================================================
# ANSWER CARD
# ======================================================================
class AnswerCard(QWidget):
    menu_requested = pyqtSignal(QPoint)
    speech_done = pyqtSignal(str)

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
        self.text.setStyleSheet("color: #FACC15; padding: 8px;")
        inner.addWidget(self.text)

        self.btn_read = self._btn("🔊 Sunayen")
        self.btn_lang = self._btn("🌐 Roman Urdu")
        self.btn_shot = self._btn("📷 Screenshot")
        self.btn_family = self._btn("📞 Family")
        self.btn_close = self._btn("✖ Band")
        self.btn_read.clicked.connect(self.read_aloud)
        self.btn_lang.clicked.connect(self.toggle_lang)
        self.btn_shot.clicked.connect(lambda: self.menu_requested.emit(QCursor.pos()))
        self.btn_family.clicked.connect(lambda: webbrowser.open(f"https://wa.me/{family_number_from_db()}"))
        self.btn_close.clicked.connect(self._close)
        self.speech_done.connect(self._on_speech_done)

        row1, row2 = QHBoxLayout(), QHBoxLayout()
        for b in (self.btn_read, self.btn_lang):
            row1.addWidget(b)
        for b in (self.btn_shot, self.btn_family, self.btn_close):
            row2.addWidget(b)
        inner.addLayout(row1)
        inner.addLayout(row2)
        outer.addWidget(self.frame)
        self.hide()

    @staticmethod
    def _btn(label):
        b = QPushButton(label)
        b.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("""
            QPushButton { background:#1F5E4D; color:white; border:2px solid #FACC15;
                          border-radius:10px; padding:8px 10px; }
            QPushButton:hover { background:#2a7a64; }
            QPushButton:disabled { background:#334155; color:#94a3b8; border-color:#64748b; }
        """)
        return b

    def show_message(self, msg, near: QWidget):
        self.text.setText(msg)
        self.btn_read.setText("🔊 Sunayen")
        self._set_buttons_enabled(False)
        self._place_near(near)
        self.show()
        self.adjustSize()
        self._place_near(near)

    def show_answer(self, en, ur, near: QWidget):
        self.english, self.roman = en, ur
        self.showing_roman = False
        self.btn_lang.setText("🌐 Roman Urdu")
        self.btn_read.setText("🔊 Sunayen")
        self.text.setText(en)
        self._set_buttons_enabled(True)
        self.show()
        self.adjustSize()
        self._place_near(near)

    def _set_buttons_enabled(self, on):
        for b in (self.btn_read, self.btn_lang):
            b.setEnabled(on)

    def toggle_lang(self):
        speaker.stop()
        self.btn_read.setText("🔊 Sunayen")
        self.showing_roman = not self.showing_roman
        self.text.setText(self.roman if self.showing_roman else self.english)
        self.btn_lang.setText("🌐 English" if self.showing_roman else "🌐 Roman Urdu")
        self.adjustSize()

    def read_aloud(self):
        if speaker.busy:                              # dobara dabane par ruk jaye
            speaker.stop()
            self.btn_read.setText("🔊 Sunayen")
            return
        self.btn_read.setText("⏹ Ruken")
        speaker.speak(self.text.text(), on_done=lambda err: self.speech_done.emit(err or ""))

    def _on_speech_done(self, err):
        self.btn_read.setText("🔊 Sunayen")
        if err:
            print("Awaaz ka masla:", err)
            self.text.setText(self.text.text() + "\n\n⚠️ Awaaz nahi chal saki.\n[" + err[:150] + "]")
            self.adjustSize()

    def _close(self):
        speaker.stop()
        self.hide()

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
# CONTROLLER: button -> (screenshot / hissa / clipboard / file) -> Claude -> card
# ======================================================================
class Controller(QObject):
    def __init__(self):
        super().__init__()
        self.button = FloatingButton()
        self.card = AnswerCard()
        self.worker = Worker()
        self.snip = None
        self.busy = False
        self.need_key = False
        self._center = QPoint(0, 0)
        self.button.clicked.connect(self._on_button)
        self.button.menu_requested.connect(self.show_menu)
        self.card.menu_requested.connect(self.show_menu)
        self.worker.answered.connect(self.on_answer)
        self.worker.failed.connect(self.on_fail)
        self.button.show()

    # ---------- menu ----------
    @pyqtSlot(QPoint)
    def show_menu(self, pos):
        m = QMenu()
        m.setStyleSheet("QMenu{font-size:16px;padding:6px;} QMenu::item{padding:9px 22px;}")
        items = [("🖥️  Poori screen parhein", "full"),
                 ("✂️  Screen ka hissa chunein", "snip"),
                 ("📋  Clipboard se parhein (copy ki hui tasveer ya text)", "clipboard"),
                 ("📁  Tasveer ki file chunein", "file")]
        for label, mode in items:
            m.addAction(label).triggered.connect(lambda _checked=False, md=mode: self.start(md))
        m.addSeparator()
        m.addAction("⏻  Mera Mohalla band karein").triggered.connect(self.quit_app)
        m.exec(pos)

    def quit_app(self):
        speaker.stop()
        QApplication.quit()

    # ---------- start ----------
    def _on_button(self):
        self.start("full")

    def start(self, mode):
        if self.busy:
            return
        if self.need_key:
            if not ensure_api_key(force=True):
                return
            self.need_key = False
        elif anthropic_client is None and not ensure_api_key():
            return
        self.busy = True
        speaker.stop()
        if mode == "clipboard":
            self._from_clipboard()
        elif mode == "file":
            self._from_file()
        else:
            # Button aur card screenshot mein na aayein, isliye pehle chhupayein
            self._center = self.button.frameGeometry().center()
            self.button.hide()
            self.card.hide()
            QTimer.singleShot(400, lambda: self._capture(mode))

    # ---------- sources ----------
    def _capture(self, mode):
        try:
            img, blank = grab_screen(self._center)
        except Exception as e:
            log_error(e)
            self.button.show()
            self.busy = False
            self.card.show_message("Screen ki tasveer nahi li ja saki.\n'📷 Screenshot' se doosra tareeqa aazmayein."
                                   + (f"\n\n[{str(e)[:200]}]" if SHOW_TECHNICAL_ERRORS else ""), self.button)
            return
        if blank:
            self.button.show()
            self.busy = False
            self.card.show_message(
                "⚠️ Yeh app apni screen parhne nahi deti (tasveer kaali ya khali aa rahi hai).\n\n"
                "Kya karein:\n"
                "1. Jo text parhwana hai usay select kar ke Ctrl+C dabayein,\n"
                "2. phir '📷 Screenshot' > 'Clipboard se parhein' dabayein.\n"
                "Ya phone se screen ki photo kheench kar 'Tasveer ki file' chunein.", self.button)
            return
        if mode == "snip":
            screen = QGuiApplication.screenAt(self._center) or QGuiApplication.primaryScreen()
            self.snip = SnipOverlay(img, screen)
            self.snip.picked.connect(self._snip_done)
            self.snip.cancelled.connect(self._snip_cancel)
            self.snip.start()
        else:
            self.button.show()
            self._ask(img=img)

    def _snip_done(self, img):
        self.snip = None
        self.button.show()
        self._ask(img=img)

    def _snip_cancel(self):
        self.snip = None
        self.busy = False
        self.button.show()

    def _from_clipboard(self):
        cb = QGuiApplication.clipboard()
        md = cb.mimeData()
        if md is not None and md.hasImage():
            qimg = cb.image()
            if not qimg.isNull():
                self._ask(img=qimage_to_pil(qimg))
                return
        if md is not None and md.hasText() and md.text().strip():
            self._ask(text=md.text().strip())
            return
        self.busy = False
        self.card.show_message(
            "📋 Clipboard khali hai.\n\nTareeqa: Windows + Shift + S dabayein, screen ka hissa chunein, "
            "phir yeh option dobara chunein.\nYa text par Ctrl+C karein.", self.button)

    def _from_file(self):
        self.card.hide()
        start_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        if not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(None, "Tasveer chunein", start_dir,
                                              "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if not path:
            self.busy = False
            return
        try:
            img = Image.open(path)
            img.load()
            img = img.convert("RGB")
        except Exception as e:
            log_error(e)
            self.busy = False
            self.card.show_message("Yeh tasveer khul nahi saki. Koi aur file chunein.", self.button)
            return
        self._ask(img=img)

    # ---------- ask Claude ----------
    def _ask(self, img=None, text=None):
        self.card.show_message("🔍 Aap ki screen parh raha hoon...\nZara intezar karein.", self.button)
        threading.Thread(target=self.worker.run, args=(img, text), daemon=True).start()

    @pyqtSlot(str, str)
    def on_answer(self, en, ur):
        self.busy = False
        self.card.show_answer(en, ur, self.button)

    @pyqtSlot(str, str)
    def on_fail(self, kind, msg):
        self.busy = False
        if kind == "key":
            self.need_key = True           # agli dafa key dobara poochi jayegi
        self.card.show_message(msg, self.button)


# ======================================================================
# DIAGNOSTIC:  python mera_mohalla.py --test
# ======================================================================
def run_selftest():
    print("=== Mera Mohalla check ===")
    key = load_api_key()
    print("1) API key:", (key[:10] + "..." + key[-4:]) if key else "NAHI MILI (api_key.txt ya ANTHROPIC_API_KEY)")
    if key:
        init_client(key)
        try:
            resp = claude_call(max_tokens=20, messages=[{"role": "user", "content": "Say OK"}])
            print("   API theek hai. Jawab:", resp.content[0].text.strip()[:40], "| model:", resp.model)
        except Exception as e:
            print("   API MASLA:", type(e).__name__, "-", str(e)[:300])
            print("  ", explain_error(e)[1])
    try:
        img, blank = grab_screen()
        out = os.path.join(BASE_DIR, "test_screenshot.png")
        img.save(out)
        print("2) Screenshot:", img.size, "->", out, "(KAALI/KHALI HAI!)" if blank else "(theek)")
    except Exception as e:
        print("2) Screenshot MASLA:", e)
    print("3) Awaaz: ab ek jumla bola jayega...")
    ok, err = speaker.speak("Assalam o alaikum. Yeh awaaz ka test hai.", wait=True)
    print("   Awaaz:", "theek" if ok else f"MASLA: {err}")
    return 0

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
            with MSS() as sct:
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
            threading.Thread(target=self._translate_with_claude, args=(text,), daemon=True).start()

    def _translate_with_claude(self, raw_text: str):
        try:
            response = anthropic_client.messages.create(
                model=MODEL,
                max_tokens=150,
                system=("You are a reassuring assistant for older adults.\n"
                        "Explain the provided technical text, error message, or button using a simple "
                        "household analogy.\nKeep your response strictly under 2 short sentences."),
                messages=[{"role": "user", "content": f"Simplify this screen text: {raw_text}"}],
            )
            self.explained.emit(response.content[0].text)
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

    if "--test" in sys.argv:
        sys.exit(run_selftest())

    if not ensure_api_key():                                               # key na ho to poochta hai
        print("API key nahi di gayi: website chalegi, lekin 'Madad' ke liye key chahiye.")
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
