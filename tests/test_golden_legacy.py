"""Golden-file regression test: verify branch USE_BUNDLE=False matches main:app.py on 50 payloads.

Covers knockout=True/False, outfield-in-GK, unknown/custom players, missing form fields,
and both threshold_mode ('tuned' and 'argmax'), comparing full JSON responses.
"""
import importlib.util
import json
import os
import random
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
# Force offline deterministic mode (prevent .env Supabase or background threads from drifting golden outputs)
os.environ['SUPABASE_URL'] = ''
os.environ['SUPABASE_KEY'] = ''
os.environ['AUTO_SYNC_ENABLED'] = '0'
os.environ['KEEP_ALIVE_ENABLED'] = '0'
os.environ['VERCEL'] = '1'
GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'golden_legacy_50.json')


def build_50_payloads(players_lite, presets, seed=42):
    p_map = {p['name']: p for p in players_lite}
    roles = ['GK', 'LB', 'CB', 'CB', 'RB', 'CM', 'CM', 'CAM', 'LW', 'ST', 'RW']
    names = [k for k, v in presets.items() if len(v.get('starters', [])) >= 11]
    rng = random.Random(seed)
    payloads = []
    while len(payloads) < 50:
        ha, hb = rng.sample(names, 2)
        st_a = [{'id': p_map[nm]['id'], 'name': nm, 'slot_pos': r}
                for nm, r in zip(presets[ha]['starters'][:11], roles) if nm in p_map]
        st_b = [{'id': p_map[nm]['id'], 'name': nm, 'slot_pos': r}
                for nm, r in zip(presets[hb]['starters'][:11], roles) if nm in p_map]
        if len(st_a) < 11 or len(st_b) < 11:
            continue
        idx = len(payloads)
        # Edge-case coverage across the 50 payloads
        if idx == 0:
            # Outfield player in GK
            st_a[0] = dict(st_a[-2], slot_pos='GK')
        elif idx == 1:
            # Unknown / custom player
            st_a[5] = {'id': None, 'name': 'Custom Test Prospect', 'slot_pos': 'CM', 'rating': 72, 'pos': 'MID'}
        pl = {
            'home_name': ha,
            'away_name': hb,
            'home_starters': st_a,
            'away_starters': st_b,
            'home_subs': [],
            'away_subs': [],
            'knockout': bool(idx % 3 == 0),
            'threshold_mode': 'argmax' if idx % 5 == 0 else 'tuned',
            'league_tier_factor': rng.choice([0.75, 0.85, 0.95, 1.00]),
        }
        if idx % 4 != 0:  # idx % 4 == 0 omits form fields to test defaults
            pl['home_form_pts'] = round(rng.uniform(0.6, 2.6), 1)
            pl['away_form_pts'] = round(rng.uniform(0.6, 2.6), 1)
        payloads.append(pl)
    return payloads


PINNED_MAIN_COMMIT = '7d67674d619f4a8bd2534a9162c6259687b01143'


def generate_golden_from_main():
    tmp_path = os.path.join(BASE_DIR, '_tmp_main_app.py')
    main_sha = subprocess.check_output(['git', 'rev-parse', PINNED_MAIN_COMMIT], cwd=BASE_DIR).decode().strip()
    src = subprocess.check_output(['git', 'show', f'{PINNED_MAIN_COMMIT}:app.py'], cwd=BASE_DIR)
    with open(tmp_path, 'wb') as f:
        f.write(src)
    try:
        spec = importlib.util.spec_from_file_location('_tmp_main_app', tmp_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._ensure_models()
        c = mod.app.test_client()
        payloads = build_50_payloads(mod.players_lite, mod.presets)
        records = []
        for pl in payloads:
            resp = c.post('/api/predict', json=pl).get_json()
            assert resp['status'] == 'success', resp
            records.append({'payload': pl, 'expected': resp})
        with open(GOLDEN_PATH, 'w', encoding='utf-8') as f:
            json.dump({'main_commit': main_sha, 'records': records}, f)
        print(f"Generated {len(records)} golden full-JSON responses from main@{main_sha[:7]} -> {GOLDEN_PATH}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def verify_branch_matches_golden():
    assert os.path.exists(GOLDEN_PATH), f"Missing golden fixture: {GOLDEN_PATH} (run with --regen to create from {PINNED_MAIN_COMMIT[:7]})"
    with open(GOLDEN_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    records = data['records']
    main_sha = data['main_commit']

    import app as branch_app
    assert branch_app.USE_BUNDLE is False, "USE_BUNDLE must be False for legacy golden check"
    branch_app._ensure_models()
    c = branch_app.app.test_client()
    for i, rec in enumerate(records):
        got = c.post('/api/predict', json=rec['payload']).get_json()
        exp = rec['expected']
        if got != exp:
            diff_keys = [k for k in set(got) | set(exp) if got.get(k) != exp.get(k)]
            raise AssertionError(f"Full-JSON mismatch at payload {i} keys={diff_keys}: got={ {k: got.get(k) for k in diff_keys} } exp={ {k: exp.get(k) for k in diff_keys} }")
    print(f"GOLDEN_LEGACY_50 PASSED: {len(records)}/50 full-JSON responses match main@{main_sha[:7]} identically (USE_BUNDLE=False).")


if __name__ == '__main__':
    if '--regen' in sys.argv:
        generate_golden_from_main()
    verify_branch_matches_golden()
