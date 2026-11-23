
import os
import time
import csv
import io
import threading
import requests
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================================
# 1. COLLEZ JUSTE VOTRE TOKEN ET VOTRE CLE ENTRE LES " "
# ==========================================================
TOKEN = "8651565062:AAHV7PeegR8P1xPKl-9x47oHKT_108cmkq4"
CHAT_ID = "8048025198"
ODDS_API_KEY = "a5b5d0b7af9a8389b06b268a71d361c6"

HEURE_ENVOI_SOIR = 22  # 22:00 Heure de Conakry (GMT)

TOKEN = str(TOKEN).strip()
if TOKEN.startswith("bot"):
    TOKEN = TOKEN[3:]
CHAT_ID = str(CHAT_ID).strip()
ODDS_API_KEY = str(ODDS_API_KEY).strip()

# ==========================================================
# 2. SERVEUR WEB POUR GARDER RENDER ACTIF 24H/24
# ==========================================================
PAGE_WEB_HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Sniper V2 - Guinee</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f172a;color:white;">
    <h1>ROBOT SNIPER V2 ACTIF</h1>
    <p>Analyse automatique des 15 derniers matchs : Corners 1ere MT et Over 2.5 Buts.</p>
</body>
</html>"""

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE_WEB_HTML.encode("utf-8"))

    def log_message(self, format, *args):
        return

def demarrer_serveur_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    server.serve_forever()

threading.Thread(target=demarrer_serveur_web, daemon=True).start()

# ==========================================================
# 3. FONCTION ENVOI TELEGRAM
# ==========================================================
def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print("Erreur Telegram:", e)

# ==========================================================
# 4. BASE DE DONNEES : STATISTIQUES DES 15 DERNIERS MATCHS
# ==========================================================
LIGUES_CSV = [
    ("Angleterre - Premier League", "E0", "eng.1"),
    ("Angleterre - Championship", "E1", "eng.2"),
    ("Espagne - La Liga", "SP1", "esp.1"),
    ("Italie - Serie A", "I1", "ita.1"),
    ("Allemagne - Bundesliga", "D1", "ger.1"),
    ("Allemagne - Bundesliga 2", "D2", "ger.2"),
    ("France - Ligue 1", "F1", "fra.1"),
    ("France - Ligue 2", "F2", "fra.2"),
    ("Pays-Bas - Eredivisie", "N1", "ned.1"),
    ("Portugal - Liga Portugal", "P1", "por.1"),
    ("Belgique - Pro League", "B1", "bel.1"),
    ("Turquie - Super Lig", "T1", "tur.1"),
    ("Ecosse - Premiership", "SC0", "sco.1")
]

def charger_historique_15_matchs():
    stats_equipes = {}
    saisons = ["2526", "2425"]

    for nom_ligue, code_csv, _ in LIGUES_CSV:
        texte_csv = None
        for s in saisons:
            url = f"https://www.football-data.co.uk/mmz4281/{s}/{code_csv}.csv"
            try:
                r = requests.get(url, 
