"""
Eastmile Discord Event Bot
---------------------------
Calcule les prochains events à partir d'horaires fixes (events_config.yaml)
et poste une alerte sur Discord via l'API REST quand un event est sur le
point de commencer.

Ne nécessite PAS de connexion permanente (pas de "gateway" Discord) :
utilise uniquement l'API REST avec le token du bot, ce qui le rend
compatible avec une exécution périodique (cron) comme GitHub Actions.

Variables d'environnement requises :
    DISCORD_BOT_TOKEN   : le token du bot Discord
    DISCORD_CHANNEL_ID  : l'ID du salon Discord où poster les alertes
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "events_config.yaml"
STATE_PATH = BASE_DIR / "state.json"

DISCORD_API = "https://discord.com/api/v10"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def send_discord_message(token: str, channel_id: str, content: str) -> None:
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={"content": content}, timeout=15)
    if resp.status_code >= 300:
        print(f"[ERREUR] Discord API {resp.status_code} : {resp.text}", file=sys.stderr)
        resp.raise_for_status()


def event_matches_day(event: dict, dt: datetime) -> bool:
    days = event.get("days", "all")
    if days == "all":
        return True
    current = dt.strftime("%a").lower()[:3]
    return current in [str(d).lower()[:3] for d in days]


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if not token or not channel_id:
        print("[ERREUR] DISCORD_BOT_TOKEN et DISCORD_CHANNEL_ID doivent être définis.", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    tz = ZoneInfo(config.get("timezone", "Europe/Paris"))
    lookahead = config.get("check_window_minutes", 7)
    now = datetime.now(tz)

    state = load_state()
    changed = False
    sent_count = 0

    for event in config["events"]:
        name = event["name"]
        emoji = event.get("emoji", "\U0001F4E2")
        lead = event.get("lead_minutes", 5)

        for time_str in event["times"]:
            hour, minute = map(int, time_str.split(":"))

            # On regarde hier / aujourd'hui / demain pour couvrir les cas
            # où la fenêtre de vérification chevauche minuit.
            for day_offset in (-1, 0, 1):
                occ_date = (now + timedelta(days=day_offset)).date()
                occ_dt = datetime.combine(
                    occ_date, datetime.min.time(), tzinfo=tz
                ).replace(hour=hour, minute=minute)

                if not event_matches_day(event, occ_dt):
                    continue

                alert_dt = occ_dt - timedelta(minutes=lead)
                delta_min = (alert_dt - now).total_seconds() / 60

                if 0 <= delta_min <= lookahead:
                    key = f"{name}|{occ_dt.isoformat()}"
                    if state.get(key):
                        continue  # déjà envoyé

                    msg = f"{emoji} **{name}** commence à {occ_dt.strftime('%H:%M')} (dans {lead} min) !"
                    send_discord_message(token, channel_id, msg)
                    print(f"Alerte envoyée : {msg}")

                    state[key] = True
                    changed = True
                    sent_count += 1

    # Nettoyage des anciennes entrées d'état (> 2 jours) pour ne pas
    # laisser grossir le fichier indéfiniment.
    cutoff = now - timedelta(days=2)
    for key in list(state.keys()):
        try:
            _, iso = key.split("|", 1)
            dt = datetime.fromisoformat(iso)
            if dt < cutoff:
                del state[key]
                changed = True
        except Exception:
            pass

    if changed:
        save_state(state)

    print(f"Terminé. {sent_count} alerte(s) envoyée(s).")


if __name__ == "__main__":
    main()
