"""
Eastmile Discord Event Bot
---------------------------
Calcule les prochains events à partir d'horaires fixes (events_config.yaml)
et poste une alerte sur Discord quand un event est sur le point de commencer.

Deux méthodes d'envoi possibles (aucune connexion permanente requise,
compatible avec une exécution périodique via cron / GitHub Actions) :

  1. Webhook (le plus simple) :
       DISCORD_WEBHOOK_URL : l'URL du webhook Discord

  2. Bot avec token (plus de possibilités, mais plus long à configurer) :
       DISCORD_BOT_TOKEN   : le token du bot Discord
       DISCORD_CHANNEL_ID  : l'ID du salon Discord où poster les alertes

Si DISCORD_WEBHOOK_URL est défini, il est utilisé en priorité.
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


def send_via_webhook(webhook_url: str, payload: dict) -> None:
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code >= 300:
        print(f"[ERREUR] Discord Webhook {resp.status_code} : {resp.text}", file=sys.stderr)
        resp.raise_for_status()


def send_via_bot(token: str, channel_id: str, payload: dict) -> None:
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code >= 300:
        print(f"[ERREUR] Discord API {resp.status_code} : {resp.text}", file=sys.stderr)
        resp.raise_for_status()


def build_event_payload(event: dict, occ_dt: datetime, ping_role_id: str | None = None) -> dict:
    """Construit un message avec un embed riche pour l'alerte d'event.

    Utilise le format de timestamp Discord <t:unix:R> qui s'affiche
    en compte à rebours relatif ("dans 5 minutes") et se met à jour
    tout seul côté client.

    Si ping_role_id est fourni, le message mentionne ce rôle (et
    autorise explicitement la mention pour que la notification parte).
    """
    name = event["name"]
    emoji = event.get("emoji", "\U0001F4E2")
    color = event.get("color", 0xF1C40F)  # jaune doré par défaut
    unix_ts = int(occ_dt.timestamp())

    embed = {
        "title": f"{emoji}  {name}",
        "description": f"Commence <t:{unix_ts}:R>  •  <t:{unix_ts}:t>",
        "color": color,
    }
    payload = {"embeds": [embed]}
    if ping_role_id:
        payload["content"] = f"<@&{ping_role_id}>"
        payload["allowed_mentions"] = {"roles": [str(ping_role_id)]}
    return payload


def event_matches_day(event: dict, dt: datetime) -> bool:
    days = event.get("days", "all")
    if days == "all":
        return True
    current = dt.strftime("%a").lower()[:3]
    return current in [str(d).lower()[:3] for d in days]


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")

    if webhook_url:
        send = lambda payload: send_via_webhook(webhook_url, payload)
    elif token and channel_id:
        send = lambda payload: send_via_bot(token, channel_id, payload)
    else:
        print(
            "[ERREUR] Configure soit DISCORD_WEBHOOK_URL, "
            "soit DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID.",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config()
    tz = ZoneInfo(config.get("timezone", "Europe/Paris"))
    lookahead = config.get("check_window_minutes", 7)
    now = datetime.now(tz)

    state = load_state()
    changed = False
    sent_count = 0
    ping_role_id = config.get("ping_role_id")

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

                    payload = build_event_payload(event, occ_dt, ping_role_id)
                    send(payload)
                    print(f"Alerte envoyée : {event['name']} à {occ_dt.strftime('%H:%M')}")

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
