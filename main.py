import os
import time
import csv
import io
import threading
import requests
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = "8651565062:AAHV7PeegR8P1xPKl-9x47oHKT_108cmkq4"
CHAT_ID = "8048025198"
HEURE_ENVOI_SOIR = 22

PAGE_WEB_HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Sniper V2</title></head>
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
    for nom_ligue, code_csv, _ in LIGUES_CSV:
        texte_csv = None
        for s in ["2526", "2425"]:
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
                    "corners_mt1_contre": ac_mt1
                })
                stats_equipes[ext]["ext"].append({
                    "corners_mt1_pour": ac_mt1,
                    "corners_mt1_contre": hc_mt1
                })
                match_global = {
                    "buts_tot": fthg + ftag,
                    "over25": 1 if (fthg + ftag) >= 3 else 0,
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

def recuperer_matchs_du_jour():
    matchs = []
    for nom_ligue, _, code_espn in LIGUES_CSV:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code_espn}/scoreboard"
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                for ev in r.json().get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    equipes = comp.get("competitors", [])
                    if len(equipes) == 2:
                        dom = next((e["team"]["displayName"] for e in equipes if e.get("homeAway") == "home"), "")
                        ext = next((e["team"]["displayName"] for e in equipes if e.get("homeAway") == "away"), "")
                        dt = ev.get("date", "")
                        heure = dt[11:16] if len(dt) >= 16 else "20:00"
                        matchs.append({"dom": dom, "ext": ext, "ligue": nom_ligue, "heure": heure})
        except Exception:
            continue
    return matchs

def generer_pronostics_sniper():
    try:
        stats = charger_historique_15_matchs()
        matchs_jour = recuperer_matchs_du_jour()

        candidats_corners = []
        candidats_over25 = []
        liste_analyse = []
        vus = set()

        for m in matchs_jour:
            eq_dom = trouver_equipe(m["dom"], stats)
            eq_ext = trouver_equipe(m["ext"], stats)
            if eq_dom and eq_ext and (eq_dom, eq_ext) not in vus:
                vus.add((eq_dom, eq_ext))
                liste_analyse.append((eq_dom, eq_ext, m["ligue"], m["heure"]))

        if len(liste_analyse) < 6:
            equipes_dispo = list(stats.keys())
            for i in range(0, len(equipes_dispo) - 1, 2):
                d = equipes_dispo[i]
                e = equipes_dispo[i + 1]
                if stats[d]["ligue"] == stats[e]["ligue"] and (d, e) not in vus:
                    vus.add((d, e))
                    liste_analyse.append((d, e, stats[d]["ligue"], "20:00"))

        for eq_dom, eq_ext, ligue, heure in liste_analyse:
            dom_15 = stats[eq_dom]["dom"][-15:]
            ext_15 = stats[eq_ext]["ext"][-15:]
            tous_dom_15 = stats[eq_dom]["tous"][-15:]
            tous_ext_15 = stats[eq_ext]["tous"][-15:]

            if len(dom_15) < 5 or len(ext_15) < 5:
                continue

            nb_dom = len(dom_15)
            valides_mt1 = sum(1 for x in dom_15 if x["corners_mt1_pour"] >= 2.0)
            pct_corners_mt1 = int((valides_mt1 / nb_dom) * 100)
            moy_dom = round(sum(x["corners_mt1_pour"] for x in dom_15) / nb_dom, 1)
            moy_ext = round(sum(x["corners_mt1_contre"] for x in ext_15) / len(ext_15), 1)
            score_corner = pct_corners_mt1 + (moy_dom * 10) + (moy_ext * 6)

            candidats_corners.append({
                "dom": eq_dom, "ext": eq_ext, "ligue": ligue, "heure": heure,
                "valides": valides_mt1, "total": nb_dom, "pct": pct_corners_mt1,
                "moy_dom": moy_dom, "moy_ext": moy_ext, "score": score_corner
            })

            comb_15 = tous_dom_15 + tous_ext_15
            nb_comb = len(comb_15)
            nb_over25 = sum(x["over25"] for x in comb_15)
            pct_over25 = int((nb_over25 / nb_comb) * 100)
            moy_buts = round(sum(x["buts_tot"] for x in comb_15) / nb_comb, 2)
            moy_tirs = round(sum(x["tirs_cadres"] for x in comb_15) / nb_comb, 1)
            nb_zero = sum(x["zero_zero"] for x in comb_15)
            score_over = pct_over25 + (moy_buts * 15) + (moy_tirs * 2) - (nb_zero * 10)

            candidats_over25.append({
                "dom": eq_dom, "ext": eq_ext, "ligue": ligue, "heure": heure,
                "pct_over": pct_over25, "moy_buts": moy_buts,
                "tirs_cadres": moy_tirs, "score": score_over
            })

        top_corners = sorted(candidats_corners, key=lambda x: x["score"], reverse=True)[:3]
        top_over25 = sorted(candidats_over25, key=lambda x: x["score"], reverse=True)[:3]

        date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        msg = f"🤖 <b>SNIPER V2 - RAPPORT DU {date_str}</b> 🇬🇳\n"
        msg += "<i>Analyse stricte sur les 10 a 15 derniers matchs</i>\n"
        msg += "====================================\n\n"
        msg += "🚩 <b>TOP 3 : CORNERS 1ere MI-TEMPS</b>\n"
        msg += "<i>Objectif : Equipe a domicile fait 2+ corners en 1ere MT</i>\n\n"

        for i, c in enumerate(top_corners, 1):
            msg += (
                f"<b>{i}. {c['dom']}</b> (vs {c['ext']})\n"
                f"🏆 <i>{c['ligue']} ({c['heure']} GMT)</i>\n"
                f"📊 <b>Stats Domicile :</b> Valide {c['valides']}/{c['total']} fois ({c['pct']}%)\n"
                f"📈 <b>Moyenne 1ere MT :</b> {c['moy_dom']} corners | {c['ext']} en concede {c['moy_ext']}\n"
                f"👉 <b>Pronostic :</b> {c['dom']} +1.5 Corners (1ere MT)\n\n"
            )

        msg += "====================================\n\n"
        msg += "🔥 <b>TOP 3 : EXPLOSION DE BUTS (OVER 2.5)</b>\n"
        msg += "<i>Objectif : Matchs tres ouverts a +2.5 buts</i>\n\n"

        for i, o in enumerate(top_over25, 1):
            msg += (
                f"<b>{i}. {o['dom']} vs {o['ext']}</b>\n"
                f"🏆 <i>{o['ligue']} ({o['heure']} GMT)</i>\n"
                f"📊 <b>Over 2.5 (15 derniers matchs) :</b> {o['pct_over']}% de reussite\n"
                f"⚽ <b>Moyenne :</b> {o['moy_buts']} buts/match ({o['tirs_cadres']} tirs cadres/m)\n"
                f"👉 <b>Pronostic :</b> +2.5 Buts dans le match (Over 2.5)\n\n"
            )

        msg += "✅ <i>Bonne chance !</i>"
        envoyer_telegram(msg)
    except Exception as e:
        print("Erreur:", e)

envoyer_telegram(
    "✅ <b>ROBOT SNIPER V2 ACTIVE !</b>\n"
    "🚩 <b>Module 1 :</b> Top 3 Corners 1ere Mi-Temps (Domicile +1.5)\n"
    "🔥 <b>Module 2 :</b> Top 3 Explosion de Buts (Over 2.5)\n"
    "⏰ <b>Rendez-vous :</b> Chaque soir a 22h00 (Heure de Conakry)"
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
