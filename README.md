# Eastmile Event Bot — Alertes Discord

Bot qui poste automatiquement des alertes dans ton salon Discord avant le
début de chaque event Eastmile, en se basant sur des horaires fixes
(pas de scraping en direct — le wiki bloque les requêtes automatisées).

Fonctionne gratuitement 24/7 via **GitHub Actions**, sans avoir besoin
de garder un PC ou un serveur allumé.

À savoir : ce n'est pas un bot "connecté en permanence" (il n'apparaîtra
pas comme "en ligne" dans la liste des membres). C'est un vrai bot Discord
(token, application dédiée) qui se réveille toutes les 5 minutes, vérifie
s'il y a un event à annoncer, poste le message, puis se rendort. Pour ce
cas d'usage (alertes programmées), c'est exactement équivalent niveau
résultat, en beaucoup plus simple et 100% gratuit.

---

## 1. Créer le bot Discord

1. Va sur https://discord.com/developers/applications
2. **New Application** → donne-lui un nom (ex: "Eastmile Events")
3. Dans le menu de gauche, va dans **Bot**
4. Clique **Reset Token** puis **Copy** pour récupérer le token
   → garde-le précieusement, tu en auras besoin à l'étape 4 (ne le partage
   jamais publiquement, ne le mets jamais directement dans le code)
5. Toujours dans **Bot**, désactive "Public Bot" si tu veux que seul toi
   puisses l'inviter
6. Va dans **OAuth2 → URL Generator**
   - Scopes : coche `bot`
   - Bot Permissions : coche `Send Messages` (et `Embed Links` si tu veux
     enrichir les messages plus tard)
7. Copie l'URL générée en bas, ouvre-la dans ton navigateur, choisis ton
   serveur et autorise le bot

## 2. Récupérer l'ID du salon Discord

1. Dans Discord, va dans **Paramètres utilisateur → Avancés** et active
   **Mode développeur**
2. Clique droit sur le salon où tu veux recevoir les alertes → **Copier
   l'ID du salon**

## 3. Créer le dépôt GitHub

1. Crée un nouveau dépôt sur GitHub (public ou privé — public = minutes
   GitHub Actions illimitées)
2. Mets-y tous les fichiers de ce projet (`check_events.py`,
   `events_config.yaml`, `requirements.txt`, `state.json`, et le dossier
   `.github/workflows/`)

## 4. Ajouter les secrets

Dans le dépôt GitHub : **Settings → Secrets and variables → Actions →
New repository secret**

- `DISCORD_BOT_TOKEN` → le token copié à l'étape 1
- `DISCORD_CHANNEL_ID` → l'ID copié à l'étape 2

## 5. Configurer les events

Ouvre `events_config.yaml` :

- Vérifie/ajuste `timezone` (compare avec le "Server time" affiché sur
  https://wiki.eastmile.org)
- Ajoute un bloc par event, sur le modèle de celui déjà présent
  (Rainbow Battle). Pour chaque event dont tu veux l'horaire, va sur sa
  page du wiki et colle-moi le texte — je te génère le bloc YAML
  correspondant si tu préfères ne pas le faire à la main.

## 6. Tester

Dans le dépôt GitHub : onglet **Actions** → sélectionne le workflow
"Eastmile Event Alerts" → **Run workflow** (bouton en haut à droite) pour
le lancer manuellement sans attendre. Regarde les logs pour voir si tout
fonctionne (et si un event tombe dans la fenêtre de vérification, le
message doit apparaître sur Discord).

Une fois testé, le workflow tourne automatiquement toutes les 5 minutes,
sans rien faire de plus.

---

## Fichiers du projet

| Fichier | Rôle |
|---|---|
| `events_config.yaml` | Liste des events et leurs horaires — c'est le fichier à modifier pour ajouter/ajuster des events |
| `check_events.py` | Script qui calcule les prochains events et poste sur Discord |
| `state.json` | Mémoire du bot pour éviter d'envoyer deux fois la même alerte (mis à jour automatiquement) |
| `.github/workflows/event-alerts.yml` | Planification : lance le script toutes les 5 minutes |
| `requirements.txt` | Dépendances Python |

## Limites connues

- GitHub Actions peut retarder légèrement l'exécution en période de forte
  charge (rarement plus de quelques minutes) — la fenêtre de vérification
  (`check_window_minutes` dans la config) absorbe ce genre de retard.
- Si Eastmile change les horaires d'un event (patch, event spécial…), il
  faudra mettre à jour `events_config.yaml` à la main — rien n'est
  automatique côté source puisque le site bloque le scraping.
