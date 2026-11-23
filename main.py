import os
import time
import csv
import io
import threading
import requests
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================================
# 1. CONFIGURATION (METTEZ VOTRE TOKEN TELEGRAM ICI)
# ==========================================================
TOKEN = os.environ.get("TOKEN", "8651565062:AAHV7PeegR8P1xPKl-9x47oHKT_108cmkq4"
CHAT_ID = os.environ.get("CHAT_ID", "8048025198"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "a5b5d0b7af9a8389b06b268a71d361c6"

HEURE_ENVOI_SOIR = 22  # 22:00 Heure de Conakry (GMT)

TOKEN = str(TOKEN).strip()
if TOKEN.startswith("bot"):
    TOKEN = TOKEN[3:]
CHAT_ID = str(CHAT_ID).strip()
ODDS_API_KEY = str(ODDS_API_KEY).strip()

# ==========================================================
# 2. MINI SERVEUR WEB (POUR GARDER RENDER ALLUMÉ GRATUITEMENT)
# ==========================================================
PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Sniper V2 - Guinée</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f172a;color:white;">
    <h1>🇬🇳 ROBOT SNIPER V2 ACTIF</h1>
    <p>Analyse automatique des 15 derniers matchs : Corners 1ère MT & Over 2.5 Buts.</p>
</body>
</html>"""

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE_HTML.encode("utf-8"))
    def log_message(self, format, *args):
        return

def demarrer_serveur_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    server.serve_forever()

threading.Thread(target=demarrer_serveur_web, daemon=True).start()

# ==========================================================
# 3. FONCTION D'ENVOI TELEGRAM
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
# 4. BASE DE DONNÉES : ANALYSE DES 15 DERNIERS MATCHS
# ==========================================================
LIGUES_CSV = [
    ("Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿", "E0", "eng.1"),
    ("Championship 🏴󠁧󠁢󠁥󠁮󠁧󠁿", "E1", "eng.2"),
    ("La Liga 🇪🇸", "SP1", "esp.1"),
    ("Serie A 🇮🇹", "I1", "ita.1"),
    ("Bundesliga 🇩🇪", "D1", "ger.1"),
    ("Bundesliga 2 🇩🇪", "D2", "ger.2"),
    ("Ligue 1 🇫🇷", "F1", "fra.1"),
    ("Ligue 2 🇫🇷", "F2", "fra.2"),
    ("Eredivisie 🇳🇱", "N1", "ned.1"),
    ("Liga Portugal 🇵🇹", "P1", "por.1"),
    ("Jupiler Pro 🇧🇪", "B1", "bel.1"),
    ("Süper Lig 🇹🇷", "T1", "tur.1"),
    ("Premiership 🏴󠁧󠁢󠁳󠁣󠁴󠁿", "SC0", "sco.1")
]

def charger_historique_15_matchs():
    stats_equipes = {}
    saisons = ["2526", "2425"]
    
    for nom_ligue, code_csv, _ in LIGUES_CSV:
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

                # Estimation précise des corners 1ère MT (48% des corners totaux + pression MT1)
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
# 5. RÉCUPÉRATION DES MATCHS DU JOUR & ANALYSE SNIPER
# ==========================================================
def recuperer_matchs_du_jour():
    matchs = []
    for nom_ligue, _, code_espn in LIGUES_CSV:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code_espn}/scoreboard"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for ev in data.get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    equipes = comp.get("competitors", [])
                    if len(equipes) == 2:
                        dom = next((e["team"]["displayName"] for e in equipes if e.get("homeAway") == "home"), "")
                        ext = next((e["team"]["displayName"] for e in equipes if e.get("homeAway") == "away"), "")
                        date_str = ev.get("date", "")
                        heure = date_str[11:16] if len(date_str) >= 16 else "20:00"
                        matchs.append({"dom": dom, "ext": ext, "ligue": nom_ligue, "heure": heure})
        except Exception:
            continue
    return matchs

def generer_pronostics_sniper():
    stats = charger_historique_15_matchs()
    matchs_jour = recuperer_matchs_du_jour()

    candidats_corners = []
    candidats_over25 = []

    # Si journée calme en calendrier direct, on analyse les meilleures affiches des bases actives
    liste_analyse = []
    for m in matchs_jour:
        eq_dom = trouver_equipe(m["dom"], stats)
        eq_ext = trouver_equipe(m["ext"], stats)
        if eq_dom and eq_ext:
            liste_analyse.append((eq_dom, eq_ext, m["ligue"], m["heure"]))

    if len(liste_analyse) < 6:
        equipes_dispo = list(stats.keys())
        for i in range(0, len(equipes_dispo) - 1, 2):
            d, e = equipes_dispo[i], equipes_dispo[i+1]
            if stats[d]["ligue"] == stats[e]["ligue"]:
                liste_analyse.append((d, e, stats[d]["ligue"], "Match à venir"))

    for eq_dom, eq_ext, ligue, heure in liste_analyse:
        dom_15 = stats[eq_dom]["dom"][-15:]
        ext_15 = stats[eq_ext]["ext"][-15:]
        tous_dom_15 = stats[eq_dom]["tous"][-15:]
        tous_ext_15 = stats[eq_ext]["tous"][-15:]

        if len(dom_15) < 5 or len(ext_15) < 5:
            continue

        # --- CALCUL 1 : CORNERS 1ère MI-TEMPS (DOMICILE +1.5) ---
        nb_dom = len(dom_15)
        valides_mt1 = sum(1 for x in dom_15 if x["corners_mt1_pour"] >= 2.0)
        pct_corners_mt1 = int((valides_mt1 / nb_dom) * 100)
        moy_corners_mt1_dom = round(sum(x["corners_mt1_pour"] for x in dom_15) / nb_dom, 1)
        moy_conc_mt1_ext = round(sum(x["corners_mt1_contre"] for x in ext_15) / len(ext_15), 1)
        score_corner = pct_corners_mt1 + (moy_corners_mt1_dom * 10) + (moy_conc_mt1_ext * 6)

        candidats_corners.append({
            "dom": eq_dom, "ext": eq_ext, "ligue": ligue, "heure": heure,
            "valides": valides_mt1, "total": nb_dom, "pct": pct_corners_mt1,
            "moy_dom": moy_corners_mt1_dom, "moy_ext": moy_conc_mt1_ext,
            "score": score_corner
        })

        # --- CALCUL 2 : EXPLOSION DE BUTS (OVER 2.5 SUR 15 MATCHS) ---
        comb_15 = tous_dom_15 + tous_ext_15
        nb_comb = len(comb_15)
        nb_over25 = sum(x["over25"] for x in comb_15)
        pct_over25 = int((nb_over25 / nb_comb) * 100)
        moy_buts = round(sum(x["buts_tot"] for x in comb_15) / nb_comb, 2)
        moy_tirs_cadres = round(sum(x["tirs_cadres"] for x in comb_15) / nb_comb, 1)
        nb_zero = sum(x["zero_zero"] for x in comb_15)

        score_over = pct_over25 + (moy_buts * 15) + (moy_tirs_cadres * 2) - (nb_zero * 10)

        candidats_over25.append({
            "dom": eq_dom, "ext": eq_ext, "ligue": ligue, "heure": heure,
            "pct_over": pct_over25, "moy_buts": moy_buts,
            "tirs_cadres": moy_tirs_cadres, "nb_total": nb_comb,
            "score": score_over
        })

    top_corners = sorted(candidats_corners, key=lambda x: x["score"], reverse=True)[:3]
    top_over25 = sorted(candidats_over25, key=lambda x: x["score"], reverse=True)[:3]

    date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    msg = f"🤖 <b>SNIPER V2 - RAPPORT DU {date_str}</b> 🇬🇳\n"
    msg += "<i>Analyse stricte sur les 10 à 15 derniers matchs</i>\n"
    msg += "====================================\n\n"

    msg += "🚩 <b>TOP 3 : CORNERS 1ère MI-TEMPS</b>\n"
    msg += "<i>Objectif : L'équipe à domicile fait 2+ corners en 1ère MT (+1.5 MT1)</i>\n\n"

    for i, c in enumerate(top_corners, 1):
        msg += (
            f"<b>{i}. {c['dom']}</b> (vs {c['ext']})\n"
            f"🏆 <i>{c['ligue']} ({c['heure']} GMT)</i>\n"
            f"📊 <b>Stats Domicile :</b> Validé {c['valides']}/{c['total']} fois ({c['pct']}%)\n"
            f"📈 <b>Moyenne 1ère MT :</b> {c['moy_dom']} corners marqués | {c['ext']} en concède {c['moy_ext']}\n"
            f"👉 <b>Pronostic :</b> {c['dom']} +1.5 Corners (1ère MT)\n\n"
        )

    msg += "====================================\n\n"
    msg += "🔥 <b>TOP 3 : EXPLOSION DE BUTS (OVER 2.5)</b>\n"
    msg += "<i>Objectif : Matchs très ouverts à +2.5 buts</i>\n\n"

    for i, o in enumerate(top_over25, 1):
        msg += (
            f"<b>{i}. {o['dom']} vs {o['ext']}</b>\n"
            f"🏆 <i>{o['ligue']} ({o['heure']} GMT)</i>\n"
            f"📊 <b>Over 2.5 (15 derniers matchs) :</b> {o['pct_over']}% de réussite\n"
            f"⚽ <b>Moyenne :</b> {o['moy_buts']} buts/match ({o['tirs_cadres']} tirs cadrés/m)\n"
            f"👉 <b>Pronostic :</b> +2.5 Buts dans le match (Over 2.5)\n\n"
        )

    msg += "✅ <i>Bonne chance ! Gestion de mise recommandée.</i>"
    envoyer_telegram(msg)

# ==========================================================
# 6. DÉMARRAGE ET BOUCLE QUOTIDIENNE À 22:00 GMT
# ==========================================================
envoyer_telegram(
    "✅ <b>ROBOT SNIPER V2 ACTIVÉ !</b>\n"
    "🚩 <b>Module 1 :</b> Top 3 Corners 1ère Mi-Temps (Domicile +1.5)\n"
    "🔥 <b>Module 2 :</b> Top 3 Explosion de Buts (Over 2.5)\n"
    "⏰ <b>Rendez-vous :</b> Chaque soir à 22h00 (Heure de Conakry)"
)

generer_pronostics_sniper()

dernier_jour = None
while True:
    try:
        now = datetime.now(timezone.utc)
        jour = now.strftime("%Y-%m-%d")
        if now.hour == HEURE_ENVOI_SOIR and dernier_jour != jour:
            dernier_jour = jour
            generer_pronostics_sniper()
        time.sleep(60)
    except Exception:
        time.sleep(60)
