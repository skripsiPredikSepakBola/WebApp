import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app import app


class TestDualDeckE2E(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_api_endpoints_exist(self):
        for ep in ['/api/health', '/api/players', '/api/presets', '/api/categories']:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 200)

    def test_symmetrical_invariance(self):
        presets = self.client.get('/api/presets').get_json()
        spain = presets.get('Spain (National Team)', {})
        england = presets.get('England (National Team)', {})
        if not spain or not england:
            self.skipTest('Supabase presets not seeded')

        payload_ab = {
            'home_name': 'Spain', 'away_name': 'England',
            'home_starters': [{'name': p, 'slot_pos': 'MID'} for p in spain.get('starters', [])[:11]],
            'away_starters': [{'name': p, 'slot_pos': 'MID'} for p in england.get('starters', [])[:11]],
            'home_subs': [], 'away_subs': [],
            'home_form_pts': 2.0, 'away_form_pts': 2.0, 'knockout': False
        }
        payload_ba = {
            'home_name': 'England', 'away_name': 'Spain',
            'home_starters': [{'name': p, 'slot_pos': 'MID'} for p in england.get('starters', [])[:11]],
            'away_starters': [{'name': p, 'slot_pos': 'MID'} for p in spain.get('starters', [])[:11]],
            'home_subs': [], 'away_subs': [],
            'home_form_pts': 2.0, 'away_form_pts': 2.0, 'knockout': False
        }

        res_ab = self.client.post('/api/predict', json=payload_ab).get_json()
        res_ba = self.client.post('/api/predict', json=payload_ba).get_json()
        self.assertAlmostEqual(res_ab['probabilities']['home'], res_ba['probabilities']['away'], places=1)
        self.assertAlmostEqual(res_ab['probabilities']['draw'], res_ba['probabilities']['draw'], places=1)

    def test_threshold_modes_in_payload(self):
        presets = self.client.get('/api/presets').get_json()
        spain = presets.get('Spain (National Team)', {})
        england = presets.get('England (National Team)', {})
        if not spain or not england:
            self.skipTest('Supabase presets not seeded')

        res = self.client.post('/api/predict', json={
            'home_name': 'Spain', 'away_name': 'England',
            'home_starters': [{'name': p, 'slot_pos': 'MID'} for p in spain.get('starters', [])[:11]],
            'away_starters': [{'name': p, 'slot_pos': 'MID'} for p in england.get('starters', [])[:11]],
            'home_subs': [], 'away_subs': [],
            'home_form_pts': 2.0, 'away_form_pts': 2.0, 'knockout': False, 'threshold_mode': 'tuned'
        }).get_json()
        self.assertIn('verdict_argmax', res)
        self.assertIn('verdict_tuned', res)
        self.assertEqual(res['threshold_tau'], 0.27)
        self.assertIn('home_crest', res)
        self.assertIn('away_crest', res)

    def test_boot_players_and_preset_meta(self):
        boot_res = self.client.get('/api/players?mode=boot')
        self.assertEqual(boot_res.status_code, 200)
        boot = boot_res.get_json()
        self.assertIsInstance(boot, list)
        self.assertGreater(len(boot), 0)
        self.assertLess(len(boot), 10000)
        self.assertTrue(all('image_url' in r and 'club_id' in r for r in boot))
        self.assertTrue(any(r.get('image_url') for r in boot[:20]))

        meta_res = self.client.get('/api/preset-meta')
        self.assertEqual(meta_res.status_code, 200)
        meta = meta_res.get_json()
        self.assertIsInstance(meta, dict)
        for key in ('Real Madrid', 'Indonesia (National Team)'):
            self.assertIn(key, meta)
            self.assertTrue(str(meta[key].get('crest_url', '')).startswith('http'))

    def test_predict_crests_and_lineup_media(self):
        presets = self.client.get('/api/presets').get_json()
        rm = presets.get('Real Madrid', {})
        id_nt = presets.get('Indonesia (National Team)', {})
        self.assertTrue(rm.get('starters'))
        self.assertTrue(id_nt.get('starters'))

        res = self.client.post('/api/predict', json={
            'home_name': 'Real Madrid', 'away_name': 'Indonesia (National Team)',
            'home_starters': [{'name': p, 'slot_pos': 'MID'} for p in rm['starters'][:11]],
            'away_starters': [{'name': p, 'slot_pos': 'MID'} for p in id_nt['starters'][:11]],
            'home_subs': [], 'away_subs': [],
            'home_form_pts': 2.2, 'away_form_pts': 1.8, 'knockout': False
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(str(data.get('home_crest', '')).startswith('http'))
        self.assertTrue(str(data.get('away_crest', '')).startswith('http'))
        self.assertTrue(all('image_url' in p and 'club_id' in p for p in data['lineups']['home']))
        self.assertTrue(all('image_url' in p and 'club_id' in p for p in data['lineups']['away']))

    def test_explore_overview(self):
        res = self.client.get('/api/explore/overview')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'success')
        for key in ('counts', 'featured_leagues', 'featured_clubs', 'featured_countries', 'top_players'):
            self.assertIn(key, data)
        self.assertGreater(data['counts']['players'], 50000)
        self.assertEqual(data['counts']['leagues'], 70)
        self.assertTrue(len(data['featured_leagues']) > 0)
        self.assertTrue(len(data['featured_clubs']) > 0)
        self.assertTrue(len(data['featured_countries']) > 0)
        self.assertTrue(len(data['top_players']) > 0)

    def test_explore_player_detail(self):
        res = self.client.get('/api/explore/player/418560')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('player', data)
        self.assertIn('seasons', data)
        self.assertIn('snapshots', data)
        self.assertEqual(data['player']['id'], 418560)
        self.assertTrue(len(data['seasons']) > 0)
        self.assertTrue(len(data['snapshots']) > 0)
        dates = [s['report_date'] for s in data['snapshots']]
        self.assertEqual(dates, sorted(dates))

    def test_explore_clubs_and_detail(self):
        for club_name in ('Persib Bandung', 'Real Madrid'):
            res = self.client.get('/api/explore/club', query_string={'name': club_name})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data.get('status'), 'success')
            for key in ('club', 'season_records', 'recent_matches', 'roster', 'preset'):
                self.assertIn(key, data)
            self.assertTrue(len(data['roster']) >= 11)
            self.assertTrue(len(data['season_records']) > 0)
            self.assertTrue(len(data['recent_matches']) > 0)
            self.assertIsNotNone(data['preset'])

        sort_val = self.client.get('/api/explore/clubs?sort=total_val&limit=10').get_json()['clubs']
        sort_rtg = self.client.get('/api/explore/clubs?sort=avg_rating&limit=10').get_json()['clubs']
        sort_sq = self.client.get('/api/explore/clubs?sort=squad_size&limit=10').get_json()['clubs']
        self.assertNotEqual([c['club_id'] for c in sort_val], [c['club_id'] for c in sort_rtg])
        self.assertNotEqual([c['club_id'] for c in sort_val], [c['club_id'] for c in sort_sq])

    def test_explore_countries_and_detail(self):
        for country_name in ('Indonesia', 'Spain'):
            res = self.client.get('/api/explore/country', query_string={'name': country_name})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data.get('status'), 'success')
            for key in ('country', 'domestic_leagues', 'top_clubs', 'top_players', 'preset'):
                self.assertIn(key, data)
            self.assertTrue(len(data['domestic_leagues']) > 0)
            self.assertTrue(len(data['top_clubs']) > 0)
            self.assertTrue(len(data['top_players']) > 0)
            self.assertIsNotNone(data['preset'])

        sort_fifa = self.client.get('/api/explore/countries?sort=fifa&limit=10').get_json()['countries']
        sort_top11 = self.client.get('/api/explore/countries?sort=top11_avg_rating&limit=10').get_json()['countries']
        self.assertNotEqual([c['name'] for c in sort_fifa], [c['name'] for c in sort_top11])

    def test_explore_leagues_and_standings(self):
        lgs = self.client.get('/api/explore/leagues')
        self.assertEqual(lgs.status_code, 200)
        lgs_data = lgs.get_json()
        self.assertEqual(len(lgs_data.get('leagues', [])), 70)

        for comp_id, season in (('IN1L', 2025), ('GB1', 2026)):
            res = self.client.get('/api/explore/league', query_string={'comp_id': comp_id, 'season': season})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data.get('status'), 'success')
            for key in ('standings', 'summary', 'top_scorers', 'top_assisters', 'top_rated', 'recent_matches'):
                self.assertIn(key, data)
            standings = data['standings']
            self.assertTrue(len(standings) > 0)
            pts = [row['pts'] for row in standings]
            self.assertEqual(pts, sorted(pts, reverse=True))
            self.assertTrue(all(not p.get('is_former') for p in data['top_rated']))

    def test_granular_roles_and_oop_matrix(self):
        from app import FORMATION_ROLES, ROLE_TO_GROUP, VALID_FORMATIONS, calculate_player_effective_rating, player_by_id
        expected_roles = {'GK', 'CB', 'LB', 'RB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'CF', 'ST'}
        for fmt in VALID_FORMATIONS:
            self.assertIn(fmt, FORMATION_ROLES)
            self.assertEqual(len(FORMATION_ROLES[fmt]), 11)
            self.assertEqual(FORMATION_ROLES[fmt][0], 'GK')
            self.assertTrue(set(FORMATION_ROLES[fmt]).issubset(expected_roles))

        boot = self.client.get('/api/players?mode=boot').get_json()
        found_roles = {p.get('role') for p in boot}
        self.assertEqual(found_roles, expected_roles)
        for p in boot[:200]:
            self.assertIn(p.get('pos'), ('GK', 'DEF', 'MID', 'ATT'))
            self.assertIn(p.get('role'), expected_roles)
            self.assertEqual(ROLE_TO_GROUP[p['role']], p['pos'])

        lw_sample = {'rating': 85.0, 'pos': 'ATT', 'role': 'LW'}
        self.assertEqual(calculate_player_effective_rating(lw_sample, 'LW'), (85.0, 0))
        self.assertEqual(calculate_player_effective_rating(lw_sample, 'RW'), (83.0, 2))
        self.assertEqual(calculate_player_effective_rating(lw_sample, 'ST'), (81.0, 4))
        self.assertEqual(calculate_player_effective_rating(lw_sample, 'ATT'), (85.0, 0))

    def test_former_players_and_legends_presets(self):
        from app import player_by_id
        for pid in (7594, 3109, 3332, 3455, 26399, 31909, 39381, 50202):
            self.assertIn(pid, player_by_id)
            self.assertTrue(player_by_id[pid].get('is_former'), f"Expected pid={pid} to have is_former=True")
            self.assertTrue(player_by_id[pid].get('former_club'), f"Expected pid={pid} to have former_club")
        self.assertEqual(player_by_id[7594].get('last_season'), 2013)
        self.assertEqual(player_by_id[7594].get('former_club'), 'FC Barcelona')
        for active_pid in (28003, 8198):
            self.assertFalse(player_by_id[active_pid].get('is_former'))

        barca = self.client.get('/api/explore/club', query_string={'name': 'FC Barcelona'}).get_json()
        self.assertEqual(barca.get('status'), 'success')
        roster_ids = {p['id'] for p in barca.get('roster', [])}
        former_ids = {p['id'] for p in barca.get('former_players', [])}
        self.assertNotIn(7594, roster_ids)
        self.assertTrue(all(not p.get('is_former') for p in barca.get('roster', [])))
        self.assertIn(7594, former_ids)

        active_pl = self.client.get('/api/explore/players?limit=50').get_json()['players']
        self.assertTrue(len(active_pl) > 0)
        self.assertTrue(all(not p.get('is_former') for p in active_pl))

        former_pl = self.client.get('/api/explore/players?status=former&limit=50').get_json()['players']
        self.assertTrue(len(former_pl) > 0)
        self.assertTrue(all(p.get('is_former') for p in former_pl))

        lw_pl = self.client.get('/api/explore/players?pos=LW&limit=30').get_json()['players']
        self.assertTrue(len(lw_pl) > 0)
        self.assertTrue(all(p.get('role') == 'LW' for p in lw_pl))

        cats = self.client.get('/api/categories').get_json()
        presets = self.client.get('/api/presets').get_json()
        self.assertIn('🏆 All-Time Legends & Icons', cats)
        for leg_team in (
            'FC Barcelona Legends',
            'Real Madrid Legends',
            'Manchester United Legends',
            'Liverpool FC Legends',
            'Premier League Icons',
            'Serie A & European Icons',
            'World XI Legends',
            'ASEAN All-Time Icons',
        ):
            self.assertIn(leg_team, cats['🏆 All-Time Legends & Icons'])
            self.assertIn(leg_team, presets)
            self.assertEqual(len(presets[leg_team]['starters']), 11)

    def test_sync_status_endpoint(self):
        res = self.client.get('/api/sync/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'ok')
        for k in ('enabled', 'running', 'supabase_configured', 'interval_sec', 'matches_synced'):
            self.assertIn(k, data)

    def test_gh_pages_model_export_equivalence(self):
        import numpy as np
        import pandas as pd
        import app as m
        from build_gh_pages import export_hgbt, eval_hgbt_row

        m._ensure_models()
        exp3 = export_hgbt(m.model_advanced_3class)
        expxg = export_hgbt(m.model_advanced_xg)

        rng = np.random.default_rng(42)
        X = pd.DataFrame(rng.normal(0.0, 2.0, size=(8, len(m.advanced_features))), columns=m.advanced_features)
        sk_probs = m.model_advanced_3class.predict_proba(X)
        sk_xg = m.model_advanced_xg.predict(X)

        for i in range(len(X)):
            row = X.iloc[i].tolist()
            raw = np.array(eval_hgbt_row(exp3, row), dtype=float)
            ex = np.exp(raw - np.max(raw))
            p_exp = ex / ex.sum()
            self.assertTrue(np.allclose(sk_probs[i], p_exp, atol=1e-6))

            xg_exp = eval_hgbt_row(expxg, row)[0]
            self.assertAlmostEqual(float(sk_xg[i]), float(xg_exp), delta=1e-6)


if __name__ == '__main__':
    unittest.main()
