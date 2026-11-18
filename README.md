# PitchPulse AI — Pre-Kickoff Tactical Football Match Engine, Standings & Global Scouting Database

**PitchPulse AI** is a full-stack pre-kickoff tactical football match simulation engine, multi-league standings explorer, and global player scouting platform built with Python, Flask, scikit-learn (`HistGradientBoostingClassifier` & `HistGradientBoostingRegressor`), and Supabase.

Designed for both production sports analytics and rigorous academic thesis (*skripsi*) evaluation, PitchPulse AI predicts 90-minute match outcomes (**Win / Draw / Loss**), dual-team **Expected Goals ($\text{xG}$)**, **6×6 Bivariate Poisson scoreline distributions**, and **individual anytime goalscorer probabilities** strictly from pre-kickoff tactical lineups, player ratings, positional fit, rolling form, and historical monthly snapshots.

---

## Key Features

### 1. 13-Role Granular Tactical Engine, Optimal Formation & Tiered Cards
- **13 Granular Tactical Roles**: Every player in the database (`71,161` players) is mapped from Transfermarkt sub-positions to one of 13 granular tactical roles across 4 line groups:
  - **Goalkeeper (`GK`)**: `GK` (Goalkeeper)
  - **Defense (`DEF`)**: `LB` (Left-Back), `CB` (Centre-Back), `RB` (Right-Back)
  - **Midfield (`MID`)**: `CDM` (Defensive Midfield), `CM` (Central Midfield), `CAM` (Attacking Midfield), `LM` (Left Midfield), `RM` (Right Midfield)
  - **Attack (`ATT`)**: `LW` (Left Winger), `RW` (Right Winger), `CF` (Second Striker / Centre-Forward), `ST` (Striker)
- **8 Supported Tactical Formations & Auto-Rearrangement**: `4-3-3`, `4-2-3-1`, `4-4-2`, `3-5-2`, `3-4-3`, `5-3-2`, `5-4-1`, `4-1-4-1`. Changing formation automatically runs `rearrangeLineupForFormation` (`fitScore`), pooling all starters and substitutes to compute the highest-rated, line-aligned Starting XI and bench.
- **Bronze / Silver / Gold Player Rating Tiers**: Pitch cards and player avatars render **Bronze (`< 72`)**, **Silver (`72–82.9`)**, and **Gold (`>= 83`)** metallic frames with face-centered portrait framing (`object-position: 50% 16%`).
- **Gameplay-Stats Player Ratings (`[52.0, 97.0]`)**: Computed in [`offline/build_gameplay_ratings.py`](offline/build_gameplay_ratings.py) from real Transfermarkt match appearances (`appearances.csv` + `games.csv`) using position-specific weighted metrics (goals/90, assists/90, goals conceded/90, clean-sheet rate, competition-weighted minutes, win contribution, cards/90 penalty, Bayesian shrinkage, and `0.52 ** (2025 - season)` recency decay for active players).
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

### 5. Match Calendar & Online Automatic Sync + Retraining
- **Interactive Match Calendar (`GET /api/calendar?month=YYYY-MM`)**: Tracks **Previous (`FT`)**, **Today (`LIVE` / scheduled)**, and **Upcoming** fixtures across European Top-5 leagues, UEFA Champions League, **UEFA Nations League A/B/C/D**, ASEAN leagues, and global API-Football fixtures, with one-click **Predict** simulation.
- **Zero-Key Transfermarkt JSON API Sync (`tmapi-alpha`)**: `sync_matches.py` queries `https://tmapi-alpha.transfermarkt.technology` across `GB1`, `ES1`, `L1`, `IT1`, `FR1`, `CL`, `UNLA`, `UNLB`, `UNLC`, `UNLD`, `IN1L`, `MYS1`, `THA1`, `VIE1`, `SIN1`, plus optional `API_FOOTBALL_KEY` (yesterday + today UTC fixtures) and `FOOTBALL_DATA_KEY` feeds into Supabase (`finished_matches`, `players`) or local/serverless cache (`local_sync_cache.json` / `/tmp/local_sync_cache.json` on Vercel).
- **GitHub Actions Automation (shared `model-state-push` concurrency group)**:
  - `.github/workflows/sync-matches.yml`: Runs `python sync_matches.py` every 6 hours (`0 */6 * * *`) to upsert recent finished matches into Supabase (`finished_matches`).
  - `.github/workflows/update-states.yml`: Runs `python update_states.py` (`rebuild_state.rebuild()`) daily at `03:00 UTC` (`0 3 * * *`) to deterministically rebuild `models/team_state.json` (`elo`, `gf10`, `ga10`, `last_date` keyed by Transfermarkt ID) and `models/league_state.json` (keyed by `competition_id`) from `models/base_state_2026-11-12.json` plus paginated post-cutoff Supabase matches (`fetch_finished_matches_paginated` with truncation guard and `AMBIGUOUS_COMP_SLUGS` cross-country guard).
  - `.github/workflows/weekly-replay.yml`: Runs Mondays at `06:00 UTC` (`0 6 * * 1`), asserts `team_state.json` `as_of` is within 2 days of the report date, runs `prospective_replay.py` (`freeze_date='2026-11-18'`), and commits only `reports/replay_YYYY-MM-DD.{json,md,log}` (skipped by Vercel `ignoreCommand`), labelled `MONITORING ONLY` until `>= 2026-12-16` and `>= 500` lineup matches.
  - `.github/workflows/retrain.yml`: Manual-only (`workflow_dispatch`, `contents: read` dry-run) gated retrain via `retrain.py` and `retrain_gate.py`.
  - `.github/workflows/ci-smoke.yml`: Python `3.11` CI running 50-payload golden legacy regression (`tests/test_golden_legacy.py`), 100-matchup F11 payload parity, 200-match CI context equivalence (`tests/equivalence_200.json`), 7-artifact Freeze SHA-256 integrity, rescaled grid & gate unit checks, legacy symmetry smoke test, and flag-on bundle smoke test (`PITCHPULSE_USE_BUNDLE=1, neutral=True`).

---

## End-to-End Data-to-Prediction Pipeline

1. **Raw Data Ingestion**:
   - Historical corpus from Transfermarkt CSVs (`games.csv`, `appearances.csv`, `game_lineups.csv`, `players.csv`, `competitions.csv`, `clubs.csv`) covering **79,060** legacy matches (`74,483` matched v3 walk-forward history matches / `148,966` rows across **74** competitions) and **71,161** players.
   - Live incremental updates via `sync_matches.py` (`tmapi-alpha`, API-Football, football-data.org) into Supabase, with deterministic ID mapping and paginated post-`2026-11-12` state rebuilds in `rebuild_state.py`.
2. **Player Rating Computation (`offline/build_gameplay_ratings.py` & `offline/build_value_ratings.py`)**:
   - Aggregates per-player appearances with competition-tier weights (`1.00` Big-5/UCL, `0.86` Major, `0.78` Standard, `0.74` ASEAN) and exponential recency decay (`0.52 ** (2025 - season)` for active players; `1.0` for Legends).
   - Computes Bayesian-shrunk per-90 gameplay metrics per position (`GK`, `DEF`, `MID`, `ATT`): goals/90, assists/90, goals conceded/90, clean-sheet rate, competition-weighted minutes, win contribution, and cards/90 penalty, mapped onto `[52.0, 97.0]` (`49,822` gameplay-rated players; point-in-time historical lookup via `max_date`).
   - Outputs `players_lite.json` and precomputed binary caches (`startup_cache.joblib`, `explorer_bundle.joblib`).
3. **Zero-Leakage Feature Engineering (`offline/build_features_from_value_ratings.py` & `features.py`)**:
   - **Legacy Live Model (`USE_BUNDLE=False`)**: Uses **16 pre-kickoff differential features** (`diff_overall_mean`, `diff_overall_max`, `diff_overall_min`, `diff_attack_vs_defense`, `diff_defense_vs_attack`, `diff_midfield`, `diff_sub_mean`, `diff_depth_gap`, `diff_market_val_log`, `diff_form_pts_5`, `diff_form_gd_5`, `diff_aerial_att_vs_def`, `diff_aerial_def_vs_att`, `diff_prime_score`, `diff_cohesion`, `league_tier_factor`).
   - **Frozen v3 Candidate Bundle (`PITCHPULSE_USE_BUNDLE=1`, tag `v3-frozen-bundle`, `models/model_bundle.joblib`)**: Prunes 10 low-signal features and uses **25 `G6+tier` features**:
     - `ANTISYMMETRIC` (7): `diff_overall_mean`, `diff_sub_mean`, `diff_market_val_log`, `diff_form_gd_5`, `diff_cohesion`, `diff_elo`, `home_flag` (`+1` Home, `0` Neutral, `-1` when mirrored Away)
     - `SYMMETRIC` (4): `sum_elo`, `league_avg_goals`, `league_home_win_rate`, `league_tier_factor`
     - `SWAP_PAIRS` (14): `own_att`/`opp_att`, `own_def`/`opp_def`, `own_gk`/`opp_gk`, `own_elo`/`opp_elo` (continuous no-pull `EloTracker`: `k=20`, `home_adv=65`, `base=1500`), `own_gf10`/`opp_gf10`, `own_ga10`/`opp_ga10` (shrunk 10-match rolling goals), `own_rest`/`opp_rest` (clamped `[1, 14]` days from `last_date` vs UTC date or explicit `match_date`).
   - Evaluated prospectively against production legacy via `prospective_replay.py` per [`replay_plan.md`](replay_plan.md) (`>= 2026-12-16` and `>= 500` lineup matches gate).
4. **Chronological Walk-Forward Training & Retraining (`retrain.py`, `retrain_gate.py`, `scoreline.py`)**:
   - **Legacy Benchmark (`<= 2021` Train `86,400` / `2022` Val `11,826` / `2023–2026` Test `59,894`)**: `HistGradientBoostingClassifier` achieves Test Acc `52.74%`, Tuned Macro-F1 `0.4666` (`tau_draw = 0.27`), LogLoss `0.9845`, Binary ROC-AUC `0.7133`, xG MAE `0.9704`.
   - **Frozen v3 Walk-Forward (`2023–2026`, `n = 29,947` pooled test matches across 4 expanding folds, `StrongReg` `max_depth=4`, `l2=6.0`, `min_samples_leaf=250`)**: Removing interleaved `season_regress` from training Elo improved LogLoss from `0.95418` (`v2`) to **`0.95212`** (`v3`, paired bootstrap `mean_gain = +0.00205`, `p5 = +0.00129`, `P(v3 > v2) = 1.000`) and RPS from `0.19873` to **`0.19801`**, with calibration `home_gap = +0.0053` and `draw_gap = -0.0077`.
   - **Region-Rescaled `11×11` Dixon-Coles Scoreline Grid (`scoreline.py`)**: Scales Poisson + Dixon-Coles regions (`rho = 0.0`, `blend_w = 0.0`) so grid Win/Draw/Loss region sums match classifier probabilities to `< 1e-9`.
   - **6-Rule Gated Promotion (`retrain_gate.py`)**: Requires `n_val_matches >= 300`, `mean_gain >= 0.002`, paired bootstrap `gain_p5 > 0.0`, `new_rps <= old_rps`, `home_gap <= 0.03`, and `draw_gap <= 0.03`.
5. **Real-Time Inference (`POST /api/predict` in `app.py`)**:
   - Resolves starters/subs (with optional `bisect_right` historical time-travel snapshot) and applies 13-role OOP penalties (`R_eff = max(35, R - Penalty)`).
   - Evaluates both `X_ab` and `X_ba` symmetrically (`0.0%` order bias when neutral or swapped on symmetrical arm).
   - Custom lineups default to `#neutral` checked (`neutral: true`); selecting a fixture from Calendar/Explorer unchecks `#neutral` automatically (`simulateFixture()`). Under `PITCHPULSE_USE_BUNDLE=1`, omitting `league_id` defaults `league_tier_factor` to `0.95` without capping confidence (`confidence` caps to `'Low'` only when `elo_missing` is `True`).

---

## Quickstart & Deployment

### Prerequisites
- **Python**: `3.11+`
- **Dependencies**: Listed in `requirements.txt` (`flask`, `pandas`, `numpy`, `joblib`, `scikit-learn`, `openpyxl`, `gunicorn`)

### 1. Local Development Setup

```bash
cd "web_app_new_v2"
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### 2. Production Vercel Deployment (`https://pitch.murfidya.app`)

The Flask backend (`app.py`) and frontend (`templates/` + `static/`) run as a single unified service on **Vercel**:

- [`vercel.json`](vercel.json): Configures `app.py` as the Flask service entrypoint.
- [`.vercelignore`](.vercelignore): Excludes raw CSVs (`player_monthly_snapshots.csv`), duplicate JSONs (`players_lite.json`, `historical_presets.json`), `_site/`, and `.env` so the bundle stays well under Vercel's 500 MB Python limit.
- Serverless-aware behavior: When `VERCEL` is set in the environment, background daemon threads are skipped and local sync caches write to `/tmp/local_sync_cache.json`.

```bash
# Deploy to Vercel production from web_app_new_v2/
vercel deploy --prod --yes
```

### 3. Production Gunicorn Deployment (`Procfile`)

```bash
gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 120
```

### 4. Rebuilding Binary Caches & Ratings

```bash
# 1. Recompute real gameplay-stats player ratings
python offline/build_gameplay_ratings.py

# 2. Rebuild explorer_bundle.joblib (leagues, standings, clubs, countries, player seasons)
python build_explorer_data.py

# 3. Rebuild startup_cache.joblib (players, boot_players, presets, compressed snapshots)
python web_app_new_v2/build_startup_cache.py
```

### 5. Running Verification & Anti-Leakage Test Suites

```bash
python tests/test_golden_legacy.py        # 50-payload legacy bit-for-bit parity (USE_BUNDLE=False)
python test_parity_and_acceptance.py      # 100 payload parity, 200 history/CI equivalence, 7 freeze hashes, gate & grid
python web_app_new_v2/test_dual_deck_e2e.py
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
| `PITCHPULSE_USE_BUNDLE` | Optional | `0` | Feature flag (`1` enables frozen v3 `G6+tier` bundle in `app.py`; kept unset/`0` during pre-registered replay). |
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
    "neutral": false,
    "league_id": "ES1",
    "match_date": "2026-11-18",
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
| `/api/calendar` | `GET` | Returns finished, live, and upcoming fixtures for a `month=YYYY-MM` (Transfermarkt + UEFA Nations League A–D + API-Football + Supabase). |
| `/api/sync` | `POST` | Triggers an immediate online sync (`sync_all()`) fetching recent finished matches from Transfermarkt (`tmapi-alpha`), API-Football (today + yesterday), and football-data.org. |
| `/api/sync/status` | `GET` | Returns real-time status of sync (`enabled`, `interval_sec`, `running`, `last_sync`, `matches_synced`, `last_result`, `last_error`, `supabase_configured`). |
| `/api/matches/recent` | `GET` | Returns the 20 most recent finished matches (`finished_matches`) and 10 most recent logged predictions (`recent_predictions`). |

---

## Repository Layout

```text
web_app_new_v2/
├── app.py                          # Flask application, dual-arm serving (USE_BUNDLE flag), 13-role OOP engine & APIs
├── elo.py                          # Continuous EloTracker (k=20, home_adv=65, base=1500, no season_regress)
├── features.py                     # Single source of truth for G6+tier (25 features), TeamState & LeagueStats
├── league_tiers.py                 # Competition quality tiers & fallback resolution
├── scoreline.py                    # 11x11 Dixon-Coles grid & region-rescaled W/D/L matching + RPS
├── retrain_gate.py                 # 6-rule chronological retrain gate (paired bootstrap p5 > 0, RPS, calibration)
├── rebuild_state.py                # Deterministic ID-mapped state builder + paginated fetch + ambiguous-slug guard
├── update_states.py                # Daily state entrypoint delegating to rebuild_state.rebuild()
├── prospective_replay.py           # Pre-registered prospective replay evaluator (legacy arm vs v3 bundle)
├── sync_matches.py                 # Transfermarkt (tmapi-alpha), API-Football, football-data.org & Calendar sync
├── retrain.py                      # Chronological retraining pipeline using ID-mapped base state & gate
├── build_startup_cache.py          # Builder for startup_cache.joblib (players, 13 roles, Legends split, snapshots)
├── vercel.json                     # Vercel Flask service configuration (skips reports/ commits)
├── .vercelignore                   # Excludes large raw CSVs & duplicate JSONs from Vercel bundle
├── apply_supabase_schema.py        # Supabase schema verifier & DDL helper
├── schema.sql                      # PostgreSQL / Supabase table definitions (5 tables)
├── academic_report_data.json       # Ground-truth evaluation metrics for thesis defense & /api/thesis-metrics
├── model_advanced_3class.joblib    # Legacy HistGradientBoostingClassifier (16 features)
├── model_advanced_xg.joblib        # Legacy HistGradientBoostingRegressor (xG)
├── advanced_feature_cols.joblib    # Ordered list of the 16 pre-kickoff legacy features
├── models/
│   ├── model_bundle.joblib         # Frozen v3 candidate bundle (G6+tier 25 features, StrongReg, Dixon-Coles)
│   ├── model_meta.json             # v3 metadata, walk-forward stats, 7 freeze SHA-256 hashes & limitations
│   ├── base_state_2026-11-12.json  # Immutable pre-cutoff Elo/last10/league snapshot & ID maps
│   ├── team_state.json             # Current Transfermarkt ID-keyed team Elo, gf10/ga10 & last_date
│   └── league_state.json           # Current competition ID-keyed avg_goals, home_win & tier
├── data/
│   └── history_features.parquet    # 74,483 matches (148,966 forward+mirrored rows) with continuous v3 Elo
├── startup_cache.joblib            # Binary startup cache (~0.2s–0.7s cold boot)
├── explorer_bundle.joblib          # Precomputed leagues, standings, clubs, countries & player career logs
├── players_lite.json               # Local fallback player catalog (71,161 players with gameplay ratings)
├── preset_lineups.json             # Active club/national presets + All-Time Legends & Icons lineups
├── preset_categories.json          # Categorized preset index
├── historical_presets.json         # Monthly historical club & national team lineups (2020-01 to 2026-11)
├── test_parity_and_acceptance.py   # Parity, 200-match history & CI equivalence, 7 freeze hashes, gate & grid suite
├── tests/
│   ├── test_golden_legacy.py       # 50-payload full-JSON golden test pinning USE_BUNDLE=False to main@7d67674
│   ├── golden_legacy_50.json       # Committed 50-payload golden fixture
│   └── equivalence_200.json        # Committed 2026-10-01 cutoff + 210-match CI equivalence fixture
├── reports/                        # Walk-forward CSVs, Elo diagnostic, mapper validation, test logs & weekly replays
├── requirements.txt                # Python 3.11 pinned dependencies (pandas 2.3.3, numpy 1.26.4, sklearn 1.6.1, pyarrow 21.0.0)
├── .python-version                 # Python runtime pin (3.11)
├── replay_plan.md                  # Pre-registered v3 prospective replay protocol & Post-freeze harness log
├── .env.example                    # Environment variable template
├── .github/workflows/
│   ├── sync-matches.yml            # 6-hour scheduled GitHub Action for match sync to Supabase
│   ├── update-states.yml           # Daily 03:00 UTC deterministic state rebuild via rebuild_state.py
│   ├── weekly-replay.yml           # Weekly Mon 06:00 UTC monitoring replay report -> reports/
│   ├── retrain.yml                 # Manual-only (workflow_dispatch) dry-run gated retrain
│   └── ci-smoke.yml                # Python 3.11 CI golden, parity, equivalence, 7 hashes & dual-arm smoke checks
├── templates/
│   └── index.html                  # PitchPulse AI single-page application template (includes #neutral switch)
├── static/
│   ├── css/style.css               # Stadium Obsidian UI stylesheet, Bronze/Silver/Gold tier frames & dark scrollbars
│   └── js/app.js                   # Frontend tactical pitch, #neutral toggle logic, Match Calendar & Explorer UI
├── README.md                       # Production engineering, pipeline & API documentation
└── THESIS_METHODOLOGY.md           # Academic thesis methodology & sidang defense reference
```
