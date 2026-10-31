# dostana
Team Name: Coderss
Members: Roha gk, Hadiah, Nooruliman, Maham Mazhar

Solution: 
Dostana is a friendly “digital neighborhood” in English and Roman Urdu where older adults practice banking, chat, email and spotting scams with fake money and short safety stories, so they can learn without fear or frustration. It keeps in mind the issues elderly people experience when using technology like falling for scams, not remembering passwords (does not require any logging in or password), language barrier, too many buttons, complex ui designs, small texts, etc.
A “Madad” button stays on their screen, reads whatever app they’re stuck on, explains it in simple words and warns about scams, then opens the matching lesson so they learn to handle it themselves next time.

Features:
Learning space- a practice space for learning real application usage with ease i.e. bank, post office, the gate, and chat with family.
Helping hand- "Madad" button which floats around over other apps to explain the current screen, warn about scams if detects some, and unlocks a story teaching about the scam.
Stories- stories which pique elder's interest are used to explain and teach about certain common dangers.
Family- keeps the family aware in case of a scam detected by the "Madad" button with just one click (uses whatsapp).
Accessibility- English and roman Urdu are supported as well as text to audio option is available.

Tech Stack: 
Language: Python
Framework: Flask
Frontend: HTML, CSS, JavaScript
Templets: Jinja2
Database: SQLite
AI Model: GPT-4o mini
Screen capture: MSS, Pillow

Build:
On cmd:
pip install flask openai pillow mss PyQt6 pyttsx3
pip install pywinauto pytesseract
On powershell:
$env:OPENROUTER_API_KEY="sk-or-v1-your-key-goes-here"
python dostana.py

Creadits:
AI agents: Claude, Gemini, OpenAI
All of our parents
