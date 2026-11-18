# Pre-Registered Prospective Replay Plan (PitchPulse AI v3 Bundle)

**Freeze Date:** `2026-11-18`
**Frozen Candidate:** `G6+tier` (25 features, `features.py`), `StrongReg` (`max_depth=4`, `min_samples_leaf=250`, `l2_regularization=6.0`), continuous no-pull `EloTracker`, region-rescaled `11x11` Dixon-Coles grid matching classifier W/D/L (`blend_w = 0.0`).
**Freeze Hashes:** Recorded in `models/model_meta.json` (`freeze_sha256`).

## Arms
- **Legacy arm:** Current production model (`model_advanced_3class.joblib` + `model_advanced_xg.joblib`, 16 features, `league_tier_factor = 0.95` default as served in production today).
- **Candidate arm:** Frozen `models/model_bundle.joblib` scored sequentially with as-of `EloTracker`, `LeagueStats`, `TeamState`, and `league_tiers.py`.

## Primary Metric & Evaluation Scope
- **Primary metric:** Paired mean log-loss gain (`logloss_legacy - logloss_new`, where `> 0` means candidate is better).
- **Secondary metrics:** RPS, calibration (`home_gap`, `draw_gap`), and **ASEAN** subset (`IN1L`, `MYS1`, `THA1`, `VIE1`, `SIN1`).
- **Evaluation window:** Only finished matches in Supabase with `match_date > 2026-11-18` that have lineups (`>= 7` starters per team).
- **Coverage reporting:** Every look must report `coverage = matches_with_lineups / all_finished_matches` alongside scores to expose lineup selection bias.

## Monitoring & Decision Rules
- **Weekly runs:** Monitoring only via `python prospective_replay.py`. No feature, hyperparameter, or threshold edits during the replay period.
- **Single-look decision rule:** Flip `USE_BUNDLE` (`PITCHPULSE_USE_BUNDLE=1`) **only after**:
  1. At least **4 weeks** elapsed since `2026-11-18` (`>= 2026-12-16`), **AND**
  2. At least **500 matches with lineups** scored, **AND**
  3. Paired bootstrap `gain_p5 > 0`, **AND**
  4. ASEAN mean log-loss gain `>= 0`, **AND**
  5. Candidate RPS `<=` Legacy RPS, **AND**
  6. Explicit user approval.
- **Stop rule:** If paired bootstrap `gain_p95 < 0` at any weekly look, stop replay and investigate immediately.

## Provenance
- **Training data cutoff:** `2026-11-12`
- **Frozen v3 bundle SHA-256 (`models/model_bundle.joblib`):** `5be979a3c365e86e3ae3289e58bbcf267a88862e1ac7d18cda79cf48a9b50506`
- **v3 vs v2 Walk-Forward (2023–2026, same folds/hyperparams, continuous no-pull Elo only change):** `LL 0.95418 -> 0.95212` (`mean_gain=+0.00205`, `p5=+0.00129`, `P(v3>v2)=1.000`), `RPS 0.19873 -> 0.19801`, `home_gap=+0.0053`, `draw_gap=-0.0077`.
- **Thesis caveat:** v3 was a second look at the same 2023–2026 folds, triggered by an implementation defect in v2's training Elo (`season_regress` firing on interleaved season labels).
- **Scored replay window:** strictly `match_date > 2026-11-18` (no overlap with training or pre-fix replay).

| Commit | Time (+0700) | What |
|---|---|---|
| `f218079` | `2026-11-17 19:32` | Freeze recipe (features, params, tier map) |
| `65f14a0` | `2026-11-18 00:45` | `model_bundle.joblib` and its SHA-256 hash committed |
| `4459c59` | `2026-11-18 01:37` | CI fix where `freeze-2026-11-17` tag points (kept unmoved) |
- **State & replay fix (`2026-11-18`):** Replaced incremental `update_states.py` with deterministic `rebuild_state.py` (keyed by Transfermarkt ID, built from `models/base_state_2026-11-12.json` without `season_regress` collapse, preserving `last10` rolling goals, skipping unmapped youth matches) and switched `prospective_replay.py` legacy arm to `app.build_legacy_feature_pair`. Any replay results generated prior to this fix are discarded.

## Part 2 Flag-Flip Prerequisites (Before `PITCHPULSE_USE_BUNDLE=1`)
In addition to the replay decision rules above, the following serving/CI fixes must land before flipping `PITCHPULSE_USE_BUNDLE=1` in production:
1. **Home/Neutral venue selector & custom lineup default:** Add a Home/Neutral venue selector in the UI, and default custom lineups to `neutral=True` (legacy model is order-symmetric, whereas the bundle gives the first-listed team home advantage unless `neutral=True`).
2. **Confidence capping on missing `league_id`:** Treat a missing `league_id` as `league_tier_factor = 0.95` without capping confidence; cap confidence to `Low` only when Elo state (`elo_missing`) is missing.
3. **CI flag-on end-to-end step:** Add a CI step in `.github/workflows/ci-smoke.yml` running `/api/predict` with `PITCHPULSE_USE_BUNDLE=1` and `neutral=True` (verifying probability sum and swap symmetry).
4. **Rest days from state:** Compute `home_rest` / `away_rest` from `last_date` in `team_state.json` (instead of defaulting to `7.0`) and cover rest days in `test_context_lookup_parity_and_mutation`.
