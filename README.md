# PitchPulse AI — Pre-Kickoff Tactical Football Match Engine, Standings & Global Scouting Database

**PitchPulse AI** is a full-stack pre-kickoff tactical football match simulation engine, multi-league standings explorer, and global player scouting platform built with Python, Flask, scikit-learn (`HistGradientBoostingClassifier` & `HistGradientBoostingRegressor`), and Supabase.

Designed for both production sports analytics and rigorous academic thesis (*skripsi*) evaluation, PitchPulse AI predicts 90-minute match outcomes (**Win / Draw / Loss**), dual-team **Expected Goals ($\text{xG}$)**, **6×6 Bivariate Poisson scoreline distributions**, and **individual anytime goalscorer probabilities** strictly from pre-kickoff tactical lineups, player ratings, positional fit, rolling form, and historical monthly snapshots.

---

## Key Features

### 1. 13-Role Granular Tactical Engine & Out-of-Position (OOP) Penalties
- **13 Granular Tactical Roles**: Every player in the database (`71,161` players) is mapped from Transfermarkt sub-positions to one of 13 granular tactical roles across 4 line groups:
  - **Goalkeeper (`GK`)**: `GK` (Goalkeeper)
  - **Defense (`DEF`)**: `LB` (Left-Back), `CB` (Centre-Back), `RB` (Right-Back)
  - **Midfield (`MID`)**: `CDM` (Defensive Midfield), `CM` (Central Midfield), `CAM` (Attacking Midfield), `LM` (Left Midfield), `RM` (Right Midfield)
  - **Attack (`ATT`)**: `LW` (Left Winger), `RW` (Right Winger), `CF` (Second Striker / Centre-Forward), `ST` (Striker)
- **8 Supported Tactical Formations**:
  - `4-3-3`: `['GK', 'LB', 'CB', 'CB', 'RB', 'CM', 'CDM', 'CM', 'LW', 'ST', 'RW']`
  - `4-2-3-1`: `['GK', 'LB', 'CB', 'CB', 'RB', 'CDM', 'CDM', 'LW', 'CAM', 'RW', 'ST']`
  - `4-4-2`: `['GK', 'LB', 'CB', 'CB', 'RB', 'LM', 'CM', 'CM', 'RM', 'ST', 'CF']`
  - `3-5-2`: `['GK', 'CB', 'CB', 'CB', 'LM', 'CDM', 'CAM', 'CM', 'RM', 'ST', 'CF']`
  - `3-4-3`: `['GK', 'CB', 'CB', 'CB', 'LM', 'CM', 'CM', 'RM', 'LW', 'ST', 'RW']`
  - `5-3-2`: `['GK', 'LB', 'CB', 'CB', 'CB', 'RB', 'CM', 'CDM', 'CM', 'ST', 'CF']`
  - `5-4-1`: `['GK', 'LB', 'CB', 'CB', 'CB', 'RB', 'LM', 'CM', 'CM', 'RM', 'ST']`
  - `4-1-4-1`: `['GK', 'LB', 'CB', 'CB', 'RB', 'CDM', 'LM', 'CM', 'CM', 'RM', 'ST']`
- **Granular Effective Rating & OOP Penalty Matrix**: Deploying a player outside their natural role applies a calibrated rating deduction before team aggregation ($R_{\text{eff}} = \max(35.0, R_{\text{base}} - \text{Penalty})$), ranging from `-1` (`ST <-> CF`) and `-2` (`LW <-> RW`, `CAM <-> CM`, `CM <-> CDM`) to `-18` (`DEF <-> ATT`) and `-40` / `-45` (`GK <-> Outfield`).

### 2. Active Squads vs. Legends & Former Icons Split
- **Strict Temporal Roster Hygiene**: Separates active 2025/2026 players (`last_season >= 2025`, `is_former: false`) from retired and former club icons (`last_season <= 2024` or inactive club status, `is_former: true`).
- **Contamination-Free Active Presets**: Present-day club and national team presets are built strictly from active players so retired legends never distort current club ratings or live match predictions.
- **Playable Legends & Club Icons**: Former icons (e.g., Carles Puyol, Toni Kroos, Wayne Rooney, Steven Gerrard, Zlatan Ibrahimović, Sergio Agüero, Gareth Bale, Eden Hazard) are preserved with `former_club` metadata and playable in dedicated **`🏆 All-Time Legends & Icons`** presets (`FC Barcelona Legends`, `Real Madrid Legends`, `Manchester United Legends`, `Liverpool FC Legends`, `Premier League Icons`, `Serie A & European Icons`, `World XI Legends`, `ASEAN All-Time Icons`), as well as inspectable under each club's **Legends & Former Icons** tab and the Scouting Hub status filter (`status=former`).

### 3. Global & ASEAN Scouting Hub + Time-Travel Snapshot Replay
- **Comprehensive Global Coverage**:
  - **71,161** players with Transfermarkt portraits, market values, career goals, goals per 90, age, height, and 13-role classifications.
  - **70** domestic and international competitions across **6** regional groups (`Top 5 European`, `Southeast Asia (ASEAN)`, `European Domestic & Cups`, `Americas & Global`, `International`), including the **5 major Southeast Asian leagues**: Indonesia Liga 1 (`IN1L`), Malaysia Super League (`MYS1`), Thai League 1 (`THA1`), V.League 1 (`VIE1`), and Singapore Premier League (`SIN1`).
  - **124** national team federations and **545** curated club, national team, and Legends presets.
- **1,046,188 Monthly Snapshots (`2020-01` to `2026-11`)**: Binary-indexed time-travel lookup (`bisect_right`) resolves exact historical squad rosters, club affiliations, market values, ages, and player ratings as of any historical month (`report_date`).

### 4. Sub-Second Startup Architecture
- **Binary Cache & C-Pickle Fast Load (`~0.7s` Cold Boot vs. `61.08s` Uncached)**:
  - `startup_cache.joblib`: Precomputes player dictionaries, normalized search blobs, preset metadata, and `zlib`-compressed snapshot/historical preset blobs.
  - `explorer_bundle.joblib`: Precomputes league tables, top scorers/assisters, club rosters, club legends, and country profiles in `zlib`-compressed byte blobs decoded lazily per route (`_exp_blob`).
- **Lazy Background Warmup & Delta Sync**:
  - Historical snapshot arrays (`_ensure_hist`) and scikit-learn models (`_ensure_models`) initialize on a background warmup thread (`_bg_warmup`) or on first inference request.
  - Non-blocking daemon sync (`_bg_supabase_delta_sync`) fetches the 200 most recently updated player records from Supabase 2 seconds after boot without delaying server readiness.
- **Two-Phase Browser Player Hydration**:
  - Phase 1 (`GET /api/players?mode=boot`): Instantly serves `boot_players` (all preset starters/substitutes plus top 2,500 players by rating) for `<300ms` interactive pitch rendering.
  - Phase 2 (`GET /api/players`): Hydrates the complete `71,161`-player database asynchronously in the background.

### 5. Online Automatic Match & Player Sync + Daily Retraining
- **Zero-Key Transfermarkt JSON API Sync (`tmapi-alpha`)**: `sync_matches.py` queries `https://tmapi-alpha.transfermarkt.technology` across top European and ASEAN competitions (`GB1`, `ES1`, `L1`, `IT1`, `FR1`, `CL`, `IN1L`, `MYS1`, `THA1`, `VIE1`, `SIN1`) to ingest finished fixtures (with starting lineups) and live squad transfers, market values, ages, and positions directly into Supabase (`finished_matches` and `players`). Optional `API_FOOTBALL_KEY` (`v3.football.api-sports.io`) and `FOOTBALL_DATA_KEY` (`api.football-data.org/v4`) feeds are also supported.
- **In-Process Auto-Sync Daemon**: Background thread (`_auto_sync_loop`) runs automatically on startup (configurable via `AUTO_SYNC_ENABLED` and `AUTO_SYNC_INTERVAL_SEC`, default every 6 hours) and exposes real-time health at `GET /api/sync/status`.
- **GitHub Actions CI/CD Pipelines**:
  - `.github/workflows/sync-matches.yml`: Runs `python sync_matches.py` on a 6-hour cron (`0 */6 * * *`).
  - `.github/workflows/retrain.yml`: Runs `python retrain.py` daily at `02:00 UTC` (`0 2 * * *`), rebuilding chronological lineup features from `finished_matches` and promoting `model_advanced_3class.joblib` and `model_advanced_xg.joblib` only when validation multi-class log-loss improves (`new_ll <= old_ll`).

---

## Quickstart & Deployment

### Prerequisites
- **Python**: `3.11+`
- **Dependencies**: Listed in `requirements.txt` (`flask`, `pandas`, `numpy`, `joblib`, `scikit-learn`, `openpyxl`, `gunicorn`)

### 1. Local Development Setup

```bash
cd "web_app_new_v2"
pip install -r requirements.txt

# Optional: copy environment template and configure Supabase credentials
cp .env.example .env

# Start the Flask server (defaults to http://127.0.0.1:5000)
python app.py
```

### 2. Zero-Provider GitHub Pages Deployment (`GitHub Pages + Actions + Supabase`)

PitchPulse AI runs 100% natively on **GitHub Pages** (`https://skripsiprediksepakbola.github.io/WebApp/`) without requiring any external Python hosting provider:

1. **Deterministic ML Tree Export (`build_gh_pages.py`)**:
   - Exports the trained `HistGradientBoostingClassifier` (`model_advanced_3class.joblib`) and `HistGradientBoostingRegressor` (`model_advanced_xg.joblib`) `TreePredictor` decision arrays into `_site/data/models.json`.
   - Exports sharded scouting/explorer bundles (`clubs_extras_shard_{0..15}.json`, `player_details_shard_{0..15}.json`, per-league JSONs, `boot_players.json`, `players_full.json`, `presets.json`) into `_site/data/`.
2. **In-Browser Inference Shim (`static/js/gh-pages-engine.js`)**:
   - When served from `*.github.io` (or static preview), intercepts `/api/*` requests and runs identical 16-feature symmetrical tree traversal, 13-role OOP penalties, Bivariate Poisson `6×6` scoring, client-side OOXML `.xlsx` generation, and sharded Scouting lookups directly in the browser (`<1e-6` numerical parity with Python `scikit-learn`).
   - When running locally via `python app.py` or Gunicorn, passes all `/api/*` traffic straight through to Flask untouched.
3. **Automated GitHub Actions CI/CD (`.github/workflows/deploy-pages.yml`)**:
   - Triggers automatically on every push to `main` and after scheduled runs of `sync-matches.yml` (every 6h) and `retrain.yml` (daily at `02:00 UTC`), rebuilding `_site/` with fresh Supabase data and publishing directly to GitHub Pages.
   - Ensure **Repository Settings → Pages → Build and deployment → Source** is set to **`GitHub Actions`**.

```bash
# Build static _site/ bundle locally for testing
python build_gh_pages.py
```

### 3. Production Gunicorn Deployment (`Procfile`)

The repository also includes a Heroku/Render/Railway-compatible `Procfile` for traditional Python server hosting:

```procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

To run with Gunicorn on Linux/container environments:

```bash
gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 120
```

#### Azure App Service Free Tier (`F1`) & 3-Layer Keep-Alive

Azure App Service Linux Free (`F1`) disables the portal **Always On** toggle. To prevent container spin-down, PitchPulse AI ships a 3-layer keep-alive architecture:

1. **In-App Daemon & On-Demand Endpoint (`app.py`)**: A background thread (`app-keep-alive`, every 600s) and `GET/POST /api/keep-alive/ping` hit the public `/api/health` URL (surfaced in `/api/health` and `/api/sync/status`).
2. **Startup Self-Pinger (`startup.sh`)**: Pulls the latest `main` commit, provisions `/tmp/antenv` on the fast local container disk (`Python 3.11`), spawns a 540s curl loop targeting `/api/health`, and launches Gunicorn (`--workers 1 --timeout 180`).
3. **External GitHub Actions Cron & GitHub Pages Beacon**: [`.github/workflows/keep-alive.yml`](.github/workflows/keep-alive.yml) (`*/14 * * * *`), [`.github/workflows/sync-matches.yml`](.github/workflows/sync-matches.yml), and active browser sessions on GitHub Pages ([`gh-pages-engine.js`](static/js/gh-pages-engine.js)) ping `/api/health` externally so cold-start idle timeouts do not reclaim the worker.

### 4. Rebuilding Binary Caches (After Data or Preset Updates)

If you modify `players_lite.json`, `preset_lineups.json`, `preset_categories.json`, or raw Transfermarkt CSV files, regenerate the precomputed bundles from the repository root:

```bash
# 1. Rebuild explorer_bundle.joblib (leagues, standings, clubs, countries, player seasons)
python build_explorer_data.py

# 2. Rebuild startup_cache.joblib (players, boot_players, presets, compressed snapshots)
python web_app_new_v2/build_startup_cache.py
```

### 5. Running Verification & Anti-Leakage Test Suites

```bash
# End-to-end Predictor, 13-Role OOP, Legends segregation, Explorer & Sync API tests
python web_app_new_v2/test_dual_deck_e2e.py

# Methodological anti-leakage & rating scaling verification (from dataset root)
python test_no_leakage.py
python test_value_ratings.py
```

---

## Environment Variables (`.env.example`)

Create a `.env` file in `web_app_new_v2/` (automatically loaded by `sync_matches._load_dotenv()`):

```ini
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY
API_FOOTBALL_KEY=YOUR_API_FOOTBALL_KEY
FOOTBALL_DATA_KEY=YOUR_FOOTBALL_DATA_ORG_TOKEN
AUTO_SYNC_ENABLED=1
AUTO_SYNC_INTERVAL_SEC=21600
PORT=5000
```

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `SUPABASE_URL` | Optional* | `""` | Supabase project URL (`https://<ref>.supabase.co`). *Falls back to local binary cache / JSON when unset.* |
| `SUPABASE_KEY` | Optional* | `""` | Supabase Service Role or PostgREST API key used for REST upserts and reads. |
| `API_FOOTBALL_KEY` | Optional | `""` | API-Football (`v3.football.api-sports.io`) key for supplementary fixture/lineup sync. |
| `FOOTBALL_DATA_KEY` | Optional | `""` | `football-data.org` v4 token for supplementary match and squad sync/backfill. |
| `AUTO_SYNC_ENABLED` | Optional | `1` | Enables (`1`/`true`) or disables (`0`/`false`) the background auto-sync daemon thread in `app.py`. |
| `AUTO_SYNC_INTERVAL_SEC` | Optional | `21600` | Interval in seconds between automatic background sync cycles (default `21600` = 6 hours). |
| `PORT` | Optional | `5000` | HTTP port bound by `app.py` or Gunicorn. |

---

## Supabase Database Setup (`schema.sql`)

Execute [`schema.sql`](file:///D:/Kaggle/Datasets/Football%20Data/web_app_new_v2/schema.sql) in the Supabase SQL Editor (or inspect migration status via `apply_supabase_schema.py`) to provision the 5 backing tables:

| Table | Primary Key | Purpose & Key Columns |
| :--- | :--- | :--- |
| `finished_matches` | `match_id TEXT` | Stores completed fixtures synced from `tmapi-alpha`, `api-football`, and `football-data.org`. Columns: `source`, `league`, `match_date TIMESTAMPTZ`, `home_team`, `away_team`, `home_goals`, `away_goals`, `status`, `raw_json JSONB` (includes starting XIs and substitutes for retraining), `synced_at`. |
| `predictions` | `id BIGINT IDENTITY` | Audit log of user match simulations. Columns: `created_at`, `home_team`, `away_team`, `p_home`, `p_draw`, `p_away`, `xg_home`, `xg_away`, `predicted_score`, `verdict`. |
| `players` | `id BIGINT` | Master player catalog (`71,161` rows). Columns: `name`, `full_name`, `tm_name`, `club`, `nat`, `pos`, `rating`, `age`, `height`, `val`, `goals_per_90`, `total_goals`, `report_date DATE DEFAULT '2026-11-01'`, `updated_at`. |
| `player_snapshots` | `(player_id, report_date)` | Historical monthly player state table. Columns: `player_id BIGINT`, `report_date DATE`, `club`, `rating`, `val`, `age`, `goals_per_90`, `total_goals`, `minutes_30d`, `goals_30d`, `assists_30d`. |
| `presets` | `name TEXT` | Preconfigured club, national team, and Legends squads. Columns: `name`, `category`, `formation TEXT DEFAULT '4-3-3'`, `starters JSONB`, `subs JSONB`. |

---

## Complete REST API Reference

### 1. Match Simulation, Tactical Lineups & Reporting

#### `POST /api/predict`
Runs symmetrical pre-kickoff match inference (`X_ab` and `X_ba` averaged), 13-role OOP rating adjustments, Expected Goals ($\text{xG}$) scaling, $6 \times 6$ Bivariate Poisson scoreline matrix generation, and individual anytime goalscorer allocation.

- **Request Body (`application/json`)**:
  ```json
  {
    "home_name": "FC Barcelona",
    "away_name": "Real Madrid",
    "home_starters": [{"id": 418560, "name": "Lamine Yamal", "slot_pos": "RW"}],
    "home_subs": ["Pedri", "Fermín López"],
    "away_starters": [{"id": 342229, "name": "Kylian Mbappé", "slot_pos": "ST"}],
    "away_subs": ["Luka Modrić", "Endrick"],
    "home_form_pts": 2.2,
    "away_form_pts": 2.0,
    "home_form_gd": 1.2,
    "away_form_gd": 0.9,
    "league_tier_factor": 0.95,
    "report_date": "2026-11",
    "knockout": false,
    "threshold_mode": "tuned"
  }
  ```
- **Response Highlights (`200 OK`)**:
  - `probabilities`: `{"home": 44.2, "draw": 24.8, "away": 31.0}`
  - `winner_key`: `'home' | 'draw' | 'away'` (defaults to `threshold_mode: "tuned"` where Draw is called at $P(\text{Draw}) \ge 27.0\%$; also returns `verdict_argmax`, `verdict_tuned`, `headline_argmax`, `headline_tuned`, `threshold_tau: 0.27`).
  - `score_prediction`: `projected_home_xg`, `projected_away_xg`, `most_likely_score`, `top_scores` (top 6 scorelines), `score_grid` ($6 \times 6$ matrix for $0..5$ goals), `over_2_5_prob`.
  - `goalscorers`: `{"home": [...], "away": [...]}` with `anytime_prob`, `expected_goals`, `effective_rating`, `oop_penalty`, `pos`, `role`, `slot_pos`.
  - `tactical_metrics`: 8 head-to-head team comparison dimensions (`Starting XI quality (effective)`, `Goalkeeper`, `Attack line`, `Midfield`, `Defence line`, `Aerial: attack height vs opp. defence (cm)`, `Age-prime factor`, `Bench depth`).
  - `knockout`: When `"knockout": true`, returns `shootout_prob`, `shootout_home`, `advance_home`, `advance_away`.

#### `GET | POST /api/snapshot`
Resolves historical or current starting XIs, substitutes, formations, and player attributes as of a target `date` / `report_date` (`YYYY-MM` or `YYYY-MM-DD`, from `2020-01` to `2026-11`).
- **Parameters / JSON Body**: `date` (or `report_date`), `auto_lineup` (`true`/`false`), `home_name`, `away_name`, `home_formation`, `away_formation`, `home_starters`, `home_subs`, `away_starters`, `away_subs`.
- **Returns**: `report_date`, `home_formation`, `away_formation`, `home_slots` (11 aligned starters), `home_subs`, `away_slots`, `away_subs`.

#### `GET /api/players`
- `?mode=boot`: Returns `boot_players` (preset starters/subs + top 2,500 players by rating) for fast initial UI mount.
- Without `mode=boot`: Returns all `71,161` players in `players_lite` (including `id`, `name`, `club`, `club_id`, `nat`, `pos`, `role`, `rating`, `age`, `height`, `val`, `goals_per_90`, `total_goals`, `image_url`, `is_former`, `last_season`, `former_club`).

#### `GET /api/players/search`
Fast server-side player autocomplete filter.
- **Query Params**: `q` (name/club/nationality substring), `role` (`GK`, `DEF`, `MID`, `ATT`, or any of the 13 granular roles `LB`, `CB`, `RB`, `CDM`, `CM`, `CAM`, `LM`, `RM`, `LW`, `RW`, `CF`, `ST`, or `SUB`), `status` (`active`, `former`, `all`), `limit` (default `30`, max `100`).

#### `GET /api/presets`, `GET /api/categories`, `GET /api/preset-meta`
- `GET /api/presets`: Dictionary of all club, national team, and `🏆 All-Time Legends & Icons` presets (`{formation, starters, subs}`).
- `GET /api/categories`: Presets grouped by competition/region category.
- `GET /api/preset-meta`: Crest URLs (`crest_url`), `club_id`, and `is_national` flags keyed by preset name.

#### `POST /api/export`
Generates and streams a formatted two-sheet Excel workbook (`match_report.xlsx` via `openpyxl`) containing an executive **Summary** sheet (with conditional formatting data bars) and a **Raw Data** sheet (lineups, effective ratings, OOP penalties, goalscorer probabilities, and full $6 \times 6$ scoreline grid).

#### `GET /api/thesis-metrics`
Returns the complete JSON evaluation report from [`academic_report_data.json`](file:///D:/Kaggle/Datasets/Football%20Data/web_app_new_v2/academic_report_data.json) (chronological split counts, 3-class & binary metrics, ROC curve points, model comparison table, ASEAN subset metrics, and permutation feature importance).

#### `GET /api/health`
Health check endpoint returning `{"status": "ok", "players": 71161}`.

---

### 2. Global & ASEAN Scouting Explorer (`/api/explore/*`)

| Endpoint | Method | Query Parameters | Description |
| :--- | :---: | :--- | :--- |
| `/api/explore/overview` | `GET` | — | Returns global entity counts (`players`, `clubs`, `countries`, `leagues`, `presets`, `snapshots`), `top_players`, `top_clubs`, `sea_leagues`, `sea_countries`, and featured cards. |
| `/api/explore/players` | `GET` | `q`, `pos` (`ALL`, 4-tier `GK/DEF/MID/ATT`, or 13-role `LW/ST/CAM/...`), `status` (`active` default, `former`, `all`), `club`, `nat`, `min_rating`, `sort` (`rating`, `val`, `goals`, `assists`), `limit` (default `40`, max `200`) | Searches and filters players across active squads or retired/former Legends. |
| `/api/explore/player/<int:player_id>` | `GET` | Path param: `player_id` | Full player dossier: biographical metadata (`foot`, `dob`, `contract`, `caps`, `int_goals`, `highest_val`, `is_former`, `last_season`, `former_club`), season-by-season career logs (`seasons`), and monthly rating/valuation trajectory (`snapshots`). |
| `/api/explore/clubs` | `GET` | `q`, `comp_id`, `country`, `sort` (`val`, `rating`/`avg_rating`, `squad`/`squad_size`, `name`), `limit` (default `40`, max `200`) | Searches clubs with active squad size, average rating, total market value, stadium, and crest URL. |
| `/api/explore/club` | `GET` | `id` (club ID) or `name` (club name) | Full club inspector: club summary, **active first-team squad (`roster`)**, **club legends & former icons (`former_players`)**, historical `season_records`, `recent_matches`, and default tactical `preset`. |
| `/api/explore/countries` | `GET` | `q`, `confederation` (`ALL`, `UEFA`, `CONMEBOL`, `AFC`, `CAF`, `CONCACAF`, `OFC`), `sort` (`fifa`, `rating`/`top11_avg_rating`, `val`/`top25_val`, `players`/`total_players`, `name`), `limit` | Lists national team federations with FIFA ranking, Top-11 average rating, Top-25 market value, and player pool size. |
| `/api/explore/country` | `GET` | `name` (country or national team name, supports aliases e.g. `usa`, `south korea`, `turkey`) | Country scouting profile: federation metadata, `domestic_leagues`, `top_clubs`, `top_players`, and national team `preset`. |
| `/api/explore/leagues` | `GET` | — | Lists all `70` competitions and regional filter groups (`regions`). |
| `/api/explore/league` | `GET` | `comp_id` (e.g. `GB1`, `IN1L`, `CL`), `season` (e.g. `2025`, `2026`) | Competition center: season summary KPIs (goals/match, home/draw/away win %, clean sheet %), full league `standings` table, `top_scorers`, `top_assisters`, `top_rated` active players, and `recent_matches`. |

---

### 3. Live Match Sync & Model Retraining Endpoints

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/sync` | `POST` | Triggers an immediate online sync (`sync_all()`) fetching recent finished matches and squad updates from Transfermarkt (`tmapi-alpha`) and configured API keys, then hot-reloads in-memory player/preset data. |
| `/api/sync/status` | `GET` | Returns real-time status of the background auto-sync daemon (`enabled`, `interval_sec`, `running`, `last_sync_at`, `last_result`, `last_error`, `supabase_configured`). |
| `/api/matches/recent` | `GET` | Returns the 20 most recent finished matches (`finished_matches`) and 10 most recent logged predictions (`recent_predictions`) from Supabase. |

---

## Repository Layout

```text
web_app_new_v2/
├── app.py                          # Flask application, 13-role tactical engine, REST API routes & auto-sync daemon
├── sync_matches.py                 # Transfermarkt (tmapi-alpha), API-Football & football-data.org -> Supabase sync
├── retrain.py                      # Chronological retraining pipeline with validation log-loss gating
├── build_startup_cache.py          # Builder for startup_cache.joblib (players, 13 roles, Legends split, snapshots)
├── build_gh_pages.py               # Static GitHub Pages generator (exports HGBT trees + sharded explorer bundles into _site/)
├── apply_supabase_schema.py        # Supabase schema verifier & DDL helper
├── schema.sql                      # PostgreSQL / Supabase table definitions (5 tables)
├── academic_report_data.json       # Ground-truth evaluation metrics for thesis defense & /api/thesis-metrics
├── model_advanced_3class.joblib    # Trained HistGradientBoostingClassifier (3-class Win/Draw/Loss)
├── model_advanced_xg.joblib        # Trained HistGradientBoostingRegressor (Expected Goals xG)
├── advanced_feature_cols.joblib    # Ordered list of the 16 pre-kickoff differential features
├── startup_cache.joblib            # Binary startup cache (~0.7s cold boot)
├── explorer_bundle.joblib          # Precomputed leagues, standings, clubs, countries & player career logs
├── players_lite.json               # Local fallback player catalog (71,161 players with role & is_former flags)
├── preset_lineups.json             # Active club/national presets + All-Time Legends & Icons lineups
├── preset_categories.json          # Categorized preset index
├── historical_presets.json         # Monthly historical club & national team lineups (2020-01 to 2026-11)
├── test_dual_deck_e2e.py           # End-to-end automated unit & integration test suite
├── requirements.txt                # Python package dependencies
├── Procfile                        # Production Gunicorn entrypoint
├── .env.example                    # Environment variable template
├── .github/workflows/
│   ├── deploy-pages.yml            # Builds _site/ and publishes to GitHub Pages on push & post-sync/retrain
│   ├── sync-matches.yml            # 6-hour scheduled GitHub Action for match & squad sync
│   └── retrain.yml                 # Daily 02:00 UTC scheduled GitHub Action for chronological model retraining
├── templates/
│   └── index.html                  # PitchPulse AI single-page application template
├── static/
│   ├── css/style.css               # Dark Broadcast Pro stylesheet
│   ├── js/gh-pages-engine.js       # Zero-server browser ML inference & API shim for GitHub Pages
│   └── js/app.js                   # Frontend tactical pitch, 13-role drag-and-drop, Bivariate Poisson heatmap & Explorer UI
├── README.md                       # Production engineering, architecture & API documentation
└── THESIS_METHODOLOGY.md           # Independent academic thesis methodology & sidang defense reference
```
