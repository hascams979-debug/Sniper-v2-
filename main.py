import os
import time
import csv
import io
import threading
import requests
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================================
# 1. CONFIGURATION (METTEZ JUSTE VOTRE CLE A LA LIGNE 15)
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
    <h1>🇬🇳 ROBOT SNIPER V2 ACTIF</h1>
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
    ("Angleterre - Premier League", "E0", "eng.1", "soccer_epl"),
    ("Angleterre - Championship", "E1", "eng.2", "soccer_efl_champ"),
    ("Espagne - La Liga", "SP1", "esp.1", "soccer_spain_la_liga"),
    ("Italie - Serie A", "I1", "ita.1", "soccer_italy_serie_a"),
    ("Allemagne - Bundesliga", "D1", "ger.1", "soccer_germany_bundesliga"),
    ("Allemagne - Bundesliga 2", "D2", "ger.2", "soccer_germany_bundesliga2"),
    ("France - Ligue 1", "F1", "fra.1", "soccer_france_ligue_one"),
    ("France - Ligue 2", "F2", "fra.2", "soccer_france_ligue_two"),
    ("Pays-Bas - Eredivisie", "N1", "ned.1", "soccer_netherlands_eredivisie"),
    ("Portugal - Liga Portugal", "P1", "por.1", "soccer_portugal_primeira_liga"),
    ("Belgique - Pro League", "B1", "bel.1", "soccer_belgium_first_div"),
    ("Turquie - Super Lig", "T1", "tur.1", "soccer_turkey_super_league"),
    ("Ecosse - Premiership", "SC0", "sco.1", "soccer_spl")
]

def charger_historique_15_matchs():
    stats_equipes = {}
    saisons = ["2526", "2425"]

    for nom_ligue, code_csv, _, _ in LIGUES_CSV:
        texte_csv = None
        for s in saisons:
            url = f"https://www.football-data.co.uk/mmz4281/{s}/{code_csv}.csv"
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200 and len(r.text) > 500:
                    texte_csv = r.text
                    break
            except Exception:
                continue
        if not texte_csv:
            continue

        lecteur = csv.DictReader(io.StringIO(texte_csv))
        for ligne in lecteur:
            try:
                dom = ligne.get("HomeTeam", "").strip()
                ext = ligne.get("AwayTeam", "").strip()
                if not dom or not ext or ligne.get("FTHG", "") == "":
                    continue

                fthg = int(float(ligne.get("FTHG", 0)))
                ftag = int(float(ligne.get("FTAG", 0)))
                hthg = int(float(ligne.get("HTHG", 0) or 0))
                htag = int(float(ligne.get("HTAG", 0) or 0))
                hc = int(float(ligne.get("HC", 0) or 0))
                ac = int(float(ligne.get("AC", 0) or 0))
                hst = int(float(ligne.get("HST", 0) or 0))
                ast = int(float(ligne.get("AST", 0) or 0))

                for eq in (dom, ext):
                    if eq not in stats_equipes:
                        stats_equipes[eq] = {"dom": [], "ext": [], "tous": [], "ligue": nom_ligue}

                hc_mt1 = round(hc * 0.48 + (0.4 if hthg + htag > 0 else 0), 1)
                ac_mt1 = round(ac * 0.48 + (0.3 if hthg + htag > 0 else 0), 1)

                stats_equipes[dom]["dom"].append({
                    "corners_mt1_pour": hc_mt1,
                    "corners_mt1_contre": ac_mt1,
                    "corners_tot": hc,
                    "buts_tot": fthg + ftag,
                    "buts_mt1": hthg + htag,
                    "tirs_cadres": hst + ast
                })
                stats_equipes[ext]["ext"].append({
                    "corners_mt1_pour": ac_mt1,
                    "corners_mt1_contre": hc_mt1,
                    "corners_tot": ac,
                    "buts_tot": fthg + ftag,
                    "buts_mt1": hthg + htag,
                    "tirs_cadres": hst + ast
                })
                match_global = {
                    "buts_tot": fthg + ftag,
                    "over25": 1 if (fthg + ftag) >= 3 else 0,
                    "btts": 1 if (fthg > 0 and ftag > 0) else 0,
                    "zero_zero": 1 if (fthg + ftag) == 0 else 0,
                    "tirs_cadres": hst + ast
                }
                stats_equipes[dom]["tous"].append(match_global)
                stats_equipes[ext]["tous"].append(match_global)
            except Exception:
                continue
    return stats_equipes

def trouver_equipe(nom_api, stats_equipes):
    nom_clean = nom_api.lower().strip()
    for eq in stats_equipes:
        eq_clean = eq.lower()
        if eq_clean == nom_clean or eq_clean in nom_clean or nom_clean in eq_clean:
            return eq
        mots = [m for m in eq_clean.split() if len(m) > 3]
        if any(m in nom_clean for m in mots):
            return eq
    return None

# ==========================================================
# 5. MATCHS DU JOUR (ODDS API + ESPN) & ANALYSE SNIPER
# ==========================================================
def recuperer_matchs_du_jour():
    matchs = []
    
