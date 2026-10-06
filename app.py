import os
import sys
import json
import math
import unicodedata
import re
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify
import joblib

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__, static_folder='static', template_folder='templates')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, '.'))

# 1. Load Player Database
print("Loading player database (50,149 players with career stats, heights, and ages)...")
with open(os.path.join(DATA_DIR, 'players_lite.json'), 'r', encoding='utf-8') as f:
    players_lite = json.load(f)

player_by_id = {p['id']: p for p in players_lite}
player_by_name = {}
for p in players_lite:
    n_lower = p['name'].lower()
    fn_lower = p['full_name'].lower()
    tm_lower = p['tm_name'].lower()
    if n_lower not in player_by_name: player_by_name[n_lower] = p
    if fn_lower not in player_by_name: player_by_name[fn_lower] = p
    if tm_lower not in player_by_name: player_by_name[tm_lower] = p

# 2. Load Presets and Categories
with open(os.path.join(DATA_DIR, 'preset_lineups.json'), 'r', encoding='utf-8') as f:
    presets = json.load(f)
with open(os.path.join(DATA_DIR, 'preset_categories.json'), 'r', encoding='utf-8') as f:
    categories = json.load(f)

# 3. Load Advanced 4-Tier Symmetrical ML Models
print("Loading advanced 4-tier ML models...")
model_advanced_3class = joblib.load(os.path.join(DATA_DIR, 'model_advanced_3class.joblib'))
model_advanced_binary = joblib.load(os.path.join(DATA_DIR, 'model_advanced_binary.joblib'))
model_advanced_xg = joblib.load(os.path.join(DATA_DIR, 'model_advanced_xg.joblib'))
advanced_features = joblib.load(os.path.join(DATA_DIR, 'advanced_feature_cols.joblib'))

# Out-of-Position (OOP) Penalty Matrix
OOP_PENALTY_MATRIX = {
    'GK':  {'GK': 0,  'DEF': 40, 'MID': 45, 'ATT': 45},
    'DEF': {'GK': 45, 'DEF': 0,  'MID': 4,  'ATT': 18},
    'MID': {'GK': 45, 'DEF': 6,  'MID': 0,  'ATT': 4},
    'ATT': {'GK': 45, 'DEF': 18, 'MID': 5,  'ATT': 0},
}

feature_display_names = {
    'diff_overall_mean': 'Starting XI Average Rating Advantage',
    'diff_overall_max': 'Star Player Peak Rating Differential',
    'diff_overall_min': 'Starting XI Weakest Link Rating',
    'diff_attack_vs_defense': 'Attack Line vs Opponent Defense Quality',
    'diff_defense_vs_attack': 'Defense Line vs Opponent Attack Quality',
    'diff_midfield': 'Midfield Playmaking & Dominance',
    'diff_sub_mean': 'Bench / Substitute Squad Quality',
    'diff_depth_gap': 'Starter-to-Bench Drop-off Continuity',
    'diff_market_val_log': 'Squad Economic Market Value (Log)',
    'diff_form_pts_5': 'Pre-Match Rolling Form Points',
    'diff_form_gd_5': 'Pre-Match Rolling Goal Difference',
    'diff_aerial_att_vs_def': 'Aerial Duel: Attack vs Opp. Defense (cm)',
    'diff_aerial_def_vs_att': 'Aerial Duel: Defense vs Opp. Attack (cm)',
    'diff_prime_score': 'Squad Physical Prime Factor (Age Curve)',
    'diff_cohesion': 'Lineup Familiarity & Shared Chemistry',
    'league_tier_factor': 'Competition Tier / League Strength'
}

def normalize_text(text):
    if not text: return ''
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()
    return ' '.join(text.split())

def resolve_player(item):
    slot_pos = None
    if isinstance(item, dict):
        slot_pos = item.get('slot_pos')
        pid = item.get('id')
        if pid and pid in player_by_id:
            p = dict(player_by_id[pid])
            p['slot_pos'] = slot_pos
            return p
        item_str = item.get('name', '')
    elif isinstance(item, int) and item in player_by_id:
        p = dict(player_by_id[item])
        p['slot_pos'] = slot_pos
        return p
    else:
        item_str = str(item)

    item_clean = normalize_text(item_str)
    p_found = None
    if item_clean in player_by_name:
        p_found = player_by_name[item_clean]
    else:
        for p in players_lite:
            if item_clean in p['full_name'].lower() or item_clean in p['name'].lower() or item_clean in p['tm_name'].lower():
                p_found = p
                break
                
    if p_found:
        res = dict(p_found)
        res['slot_pos'] = slot_pos
        return res
    return None

def calculate_player_effective_rating(p, slot_pos):
    native_pos = p.get('pos', 'MID')
    base_rating = float(p.get('rating', 75))
    if not slot_pos or slot_pos == 'SUB':
        return base_rating, 0
    penalty = OOP_PENALTY_MATRIX.get(native_pos, {}).get(slot_pos, 0)
    eff_rating = max(35.0, base_rating - penalty)
    return eff_rating, penalty

def aggregate_team_advanced(starters_input, subs_input, team_name="Team"):
    starters = [resolve_player(p) for p in starters_input]
    starters = [p for p in starters if p is not None]
    
    subs = [resolve_player(p) for p in subs_input]
    subs = [p for p in subs if p is not None]
    
    if not starters:
        raise ValueError(f"No valid starting players resolved for {team_name}")
        
    df_st = pd.DataFrame(starters)
    df_sb = pd.DataFrame(subs) if subs else pd.DataFrame()
    
    if 'height' not in df_st: df_st['height'] = 182.0
    if 'age' not in df_st: df_st['age'] = 26.0
    
    # Calculate Out-of-Position (OOP) Effective Ratings
    effective_ratings = []
    oop_penalties = []
    has_outfield_in_gk = False
    
    for _, row in df_st.iterrows():
        p_obj = row.to_dict()
        slot_p = p_obj.get('slot_pos', p_obj.get('pos', 'MID'))
        eff_r, pen = calculate_player_effective_rating(p_obj, slot_p)
        effective_ratings.append(eff_r)
        oop_penalties.append(pen)
        if slot_p == 'GK' and p_obj.get('pos') != 'GK':
            has_outfield_in_gk = True
            
    df_st['effective_rating'] = effective_ratings
    df_st['oop_penalty'] = oop_penalties
    
    stats = {}
    stats['starter_count'] = len(df_st)
    stats['starter_overall_mean'] = float(df_st['effective_rating'].mean())
    stats['starter_overall_max'] = float(df_st['effective_rating'].max())
    stats['starter_overall_min'] = float(df_st['effective_rating'].min())
    stats['starter_market_val_sum'] = float(df_st['val'].sum())
    stats['starter_height_mean'] = float(df_st['height'].mean())
    stats['starter_age_mean'] = float(df_st['age'].mean())
    stats['has_outfield_in_gk'] = has_outfield_in_gk
    
    prime_scores = (1.0 - 0.018 * (df_st['age'] - 27.0).abs()**1.25).clip(0.6, 1.0)
    stats['starter_prime_mean'] = float(prime_scores.mean())
    
    def line_metric(slot_label, col, fallback):
        sub = df_st[df_st['slot_pos'] == slot_label]
        if len(sub) == 0:
            sub = df_st[df_st['pos'] == slot_label]
        return float(sub[col].mean()) if len(sub) > 0 else fallback
        
    stats['overall_mean_GK'] = line_metric('GK', 'effective_rating', stats['starter_overall_mean'])
    stats['overall_mean_DEF'] = line_metric('DEF', 'effective_rating', stats['starter_overall_mean'])
    stats['overall_mean_MID'] = line_metric('MID', 'effective_rating', stats['starter_overall_mean'])
    stats['overall_mean_ATT'] = line_metric('ATT', 'effective_rating', stats['starter_overall_mean'])
    
    stats['height_mean_DEF'] = line_metric('DEF', 'height', stats['starter_height_mean'])
    stats['height_mean_ATT'] = line_metric('ATT', 'height', stats['starter_height_mean'])
    
    if len(df_sb) > 0:
        stats['sub_count'] = len(df_sb)
        stats['sub_overall_mean'] = float(df_sb['rating'].mean())
        stats['sub_overall_max'] = float(df_sb['rating'].max())
    else:
        stats['sub_count'] = 0
        stats['sub_overall_mean'] = stats['starter_overall_mean'] - 5.0
        stats['sub_overall_max'] = stats['starter_overall_mean']
        
    stats['depth_gap'] = stats['starter_overall_mean'] - stats['sub_overall_mean']
    return stats, starters, subs

def compute_player_scorers(players, team_xg):
    pos_weights = {'ATT': 1.0, 'MID': 0.40, 'DEF': 0.08, 'GK': 0.001}
    scored_list = []
    
    weights = []
    for p in players:
        slot_p = p.get('slot_pos', p.get('pos', 'MID'))
        if slot_p == 'GK':
            pos_mult = 0.001 # Goalkeeper in goal almost never scores
        else:
            pos_mult = pos_weights.get(slot_p, 0.4)
            
        g90 = p.get('goals_per_90', 0.2)
        eff_r, _ = calculate_player_effective_rating(p, slot_p)
        w = pos_mult * (0.3 * (eff_r / 80.0) + 0.7 * max(0.05, g90))
        weights.append(w)
        
    total_w = sum(weights) or 1.0
    for p, w in zip(players, weights):
        share = w / total_w
        indiv_xg = team_xg * share
        anytime_prob = 1.0 - math.exp(-indiv_xg)
        eff_r, pen = calculate_player_effective_rating(p, p.get('slot_pos', p.get('pos')))
        scored_list.append({
            'name': p['name'],
            'pos': p.get('pos', 'MID'),
            'slot_pos': p.get('slot_pos', p.get('pos', 'MID')),
            'rating': p.get('rating', 75),
            'effective_rating': round(eff_r, 1),
            'oop_penalty': pen,
            'height': p.get('height', 182),
            'age': p.get('age', 26),
            'club': p.get('club', ''),
            'career_goals': p.get('total_goals', 0),
            'goals_per_90': p.get('goals_per_90', 0.0),
            'anytime_prob': round(anytime_prob * 100, 1),
            'expected_goals': round(indiv_xg, 2)
        })
    return sorted(scored_list, key=lambda x: x['anytime_prob'], reverse=True)

def compute_xai_feature_attributions(X_base, p_base_a):
    attributions = []
    for col in advanced_features:
        if col == 'league_tier_factor': continue
        
        X_perturbed = X_base.copy()
        val_original = float(X_base[col].iloc[0])
        X_perturbed[col] = 0.0
        
        prob_pert = model_advanced_3class.predict_proba(X_perturbed)[0][2]
        delta = (p_base_a - prob_pert) * 100.0
        
        if abs(delta) >= 0.1 or abs(val_original) >= 0.1:
            attributions.append({
                'feature': col,
                'name': feature_display_names.get(col, col),
                'value': round(val_original, 2),
                'impact_pct': round(delta, 1),
                'is_positive': bool(delta >= 0)
            })
            
    attributions.sort(key=lambda x: abs(x['impact_pct']), reverse=True)
    return attributions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/players')
def get_players():
    return jsonify(players_lite)

@app.route('/api/presets')
def get_presets():
    return jsonify(presets)

@app.route('/api/categories')
def get_categories():
    return jsonify(categories)

@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json() or {}
        team_a_name = data.get('home_name', 'Squad 1')
        team_b_name = data.get('away_name', 'Squad 2')
        
        starters_a = data.get('home_starters', [])
        subs_a = data.get('home_subs', [])
        starters_b = data.get('away_starters', [])
        subs_b = data.get('away_subs', [])
        
        form_pts_a = float(data.get('home_form_pts', 1.8))
        form_pts_b = float(data.get('away_form_pts', 1.8))
        form_gd_a = float(data.get('home_form_gd', 0.5))
        form_gd_b = float(data.get('away_form_gd', 0.5))
        
        stats_a, st_a, sb_a = aggregate_team_advanced(starters_a, subs_a, team_a_name)
        stats_b, st_b, sb_b = aggregate_team_advanced(starters_b, subs_b, team_b_name)
        
        features_ab = {
            'diff_overall_mean': stats_a['starter_overall_mean'] - stats_b['starter_overall_mean'],
            'diff_overall_max': stats_a['starter_overall_max'] - stats_b['starter_overall_max'],
            'diff_overall_min': stats_a['starter_overall_min'] - stats_b['starter_overall_min'],
            'diff_attack_vs_defense': stats_a['overall_mean_ATT'] - stats_b['overall_mean_DEF'],
            'diff_defense_vs_attack': stats_a['overall_mean_DEF'] - stats_b['overall_mean_ATT'],
            'diff_midfield': stats_a['overall_mean_MID'] - stats_b['overall_mean_MID'],
            'diff_sub_mean': stats_a['sub_overall_mean'] - stats_b['sub_overall_mean'],
            'diff_depth_gap': stats_a['depth_gap'] - stats_b['depth_gap'],
            'diff_market_val_log': np.log1p(stats_a['starter_market_val_sum']) - np.log1p(stats_b['starter_market_val_sum']),
            'diff_form_pts_5': form_pts_a - form_pts_b,
            'diff_form_gd_5': form_gd_a - form_gd_b,
            'diff_aerial_att_vs_def': stats_a['height_mean_ATT'] - stats_b['height_mean_DEF'],
            'diff_aerial_def_vs_att': stats_a['height_mean_DEF'] - stats_b['height_mean_ATT'],
            'diff_prime_score': stats_a['starter_prime_mean'] - stats_b['starter_prime_mean'],
            'diff_cohesion': 0.0,
            'league_tier_factor': 0.95
        }
        
        X_ab = pd.DataFrame([features_ab])[advanced_features]
        
        features_ba = {
            'diff_overall_mean': -features_ab['diff_overall_mean'],
            'diff_overall_max': -features_ab['diff_overall_max'],
            'diff_overall_min': -features_ab['diff_overall_min'],
            'diff_attack_vs_defense': -features_ab['diff_defense_vs_attack'],
            'diff_defense_vs_attack': -features_ab['diff_attack_vs_defense'],
            'diff_midfield': -features_ab['diff_midfield'],
            'diff_sub_mean': -features_ab['diff_sub_mean'],
            'diff_depth_gap': -features_ab['diff_depth_gap'],
            'diff_market_val_log': -features_ab['diff_market_val_log'],
            'diff_form_pts_5': -features_ab['diff_form_pts_5'],
            'diff_form_gd_5': -features_ab['diff_form_gd_5'],
            'diff_aerial_att_vs_def': -features_ab['diff_aerial_def_vs_att'],
            'diff_aerial_def_vs_att': -features_ab['diff_aerial_att_vs_def'],
            'diff_prime_score': -features_ab['diff_prime_score'],
            'diff_cohesion': -features_ab['diff_cohesion'],
            'league_tier_factor': features_ab['league_tier_factor']
        }
        X_ba = pd.DataFrame([features_ba])[advanced_features]
        
        # 1. 3-Class Probabilities
        prob_ab = model_advanced_3class.predict_proba(X_ab)[0]
        prob_ba = model_advanced_3class.predict_proba(X_ba)[0]
        
        p_a_win = float((prob_ab[2] + prob_ba[0]) / 2.0)
        p_b_win = float((prob_ab[0] + prob_ba[2]) / 2.0)
        p_draw = float((prob_ab[1] + prob_ba[1]) / 2.0)
        
        # 2. Binary Win Confidence
        bin_prob_a = float(model_advanced_binary.predict_proba(X_ab)[0][1])
        bin_prob_b = float(model_advanced_binary.predict_proba(X_ba)[0][1])
        final_bin_a = (bin_prob_a + (1.0 - bin_prob_b)) / 2.0
        
        # 3. Expected Goals (xG) with Absolute Offensive Firepower Scaling
        xg_base_a = max(0.4, float(model_advanced_xg.predict(X_ab)[0]))
        xg_base_b = max(0.4, float(model_advanced_xg.predict(X_ba)[0]))
        
        # Absolute offensive scaling & defensive resistance
        att_g90_a = float(pd.DataFrame(st_a)['goals_per_90'].nlargest(3).sum()) if st_a else 0.8
        att_g90_b = float(pd.DataFrame(st_b)['goals_per_90'].nlargest(3).sum()) if st_b else 0.8
        
        att_mult_a = ((stats_a['overall_mean_ATT'] / 78.0) ** 1.25) * (1.0 + (att_g90_a - 0.7) / 3.2)
        att_mult_b = ((stats_b['overall_mean_ATT'] / 78.0) ** 1.25) * (1.0 + (att_g90_b - 0.7) / 3.2)
        
        def_supp_a = (stats_a['overall_mean_DEF'] / 78.0) ** 0.5
        def_supp_b = (stats_b['overall_mean_DEF'] / 78.0) ** 0.5
        
        form_boost_a = 0.88 + 0.12 * (form_pts_a / 2.0)
        form_boost_b = 0.88 + 0.12 * (form_pts_b / 2.0)
        
        xg_a = max(0.3, xg_base_a * (att_mult_a / def_supp_b) * form_boost_a)
        xg_b = max(0.3, xg_base_b * (att_mult_b / def_supp_a) * form_boost_b)
        
        # If Squad A has an outfield player in goal (e.g. Messi as GK), Opponent xG doubles!
        if stats_a['has_outfield_in_gk']:
            xg_b = xg_b * 2.2 + 1.2
            p_b_win = min(0.92, p_b_win * 1.8 + 0.35)
            p_a_win = max(0.04, p_a_win * 0.25)
            p_draw = max(0.04, 1.0 - p_a_win - p_b_win)
            final_bin_a = max(0.05, final_bin_a * 0.2)
            
        if stats_b['has_outfield_in_gk']:
            xg_a = xg_a * 2.2 + 1.2
            p_a_win = min(0.92, p_a_win * 1.8 + 0.35)
            p_b_win = max(0.04, p_b_win * 0.25)
            p_draw = max(0.04, 1.0 - p_a_win - p_b_win)
            final_bin_a = min(0.95, final_bin_a * 1.8 + 0.35)
            
        # Generate Bivariate Poisson Exact Score Matrix
        score_matrix = []
        for ga in range(6):
            for gb in range(6):
                p_ga = (math.pow(xg_a, ga) * math.exp(-xg_a)) / math.factorial(ga)
                p_gb = (math.pow(xg_b, gb) * math.exp(-xg_b)) / math.factorial(gb)
                prob = p_ga * p_gb
                score_matrix.append({
                    'score': f"{ga} - {gb}",
                    'team_a_goals': ga,
                    'team_b_goals': gb,
                    'prob': round(prob * 100, 1)
                })
                
        score_matrix.sort(key=lambda x: x['prob'], reverse=True)
        top_score = score_matrix[0]
        
        # Rigorous Match Verdict Determination
        diff_p = p_a_win - p_b_win
        top_is_draw = (top_score['team_a_goals'] == top_score['team_b_goals'])
        
        if top_is_draw and abs(diff_p) < 0.14:
            winner_key = "draw"
            winner_label = f"Draw Projected ({top_score['score']})"
            bin_verdict = f"Draw Likely • Deadlock ({final_bin_a * 100:.1f}% vs {(1.0 - final_bin_a) * 100:.1f}%)"
        elif abs(diff_p) < 0.05 or (p_draw >= p_a_win and p_draw >= p_b_win):
            winner_key = "draw"
            winner_label = f"Draw Projected (Even Contest)"
            bin_verdict = f"Draw Likely • Even Clash"
        elif diff_p >= 0.05:
            winner_key = "team_a"
            winner_label = f"{team_a_name} Victory Projected"
            bin_verdict = f"{team_a_name} Favored to Win ({final_bin_a * 100:.1f}%)"
        else:
            winner_key = "team_b"
            winner_label = f"{team_b_name} Victory Projected"
            bin_verdict = f"{team_b_name} Favored to Win ({(1.0 - final_bin_a) * 100:.1f}%)" 
        
        scorers_a = compute_player_scorers(st_a, xg_a)
        scorers_b = compute_player_scorers(st_b, xg_b)
        xai_breakdown = compute_xai_feature_attributions(X_ab, p_a_win)
        
        # Inject Outfield in Goal Warning if active
        if stats_a['has_outfield_in_gk']:
            xai_breakdown.insert(0, {
                'feature': 'outfield_in_gk',
                'name': '🚨 Outfield Player Playing in Goal (Severe Blunder)',
                'value': -45.0,
                'impact_pct': -45.0,
                'is_positive': False
            })
        if stats_b['has_outfield_in_gk']:
            xai_breakdown.insert(0, {
                'feature': 'outfield_in_gk',
                'name': f'🎯 Opponent Outfield Player in Goal ({team_a_name} Easy xG Boost)',
                'value': 45.0,
                'impact_pct': 45.0,
                'is_positive': True
            })
        
        return jsonify({
            'status': 'success',
            'winner_key': winner_key,
            'winner_label': winner_label,
            'probabilities': {
                'home': round(p_a_win * 100, 1),
                'draw': round(p_draw * 100, 1),
                'away': round(p_b_win * 100, 1)
            },
            'binary_mode': {
                'home_win_probability': round(final_bin_a * 100, 1),
                'verdict': bin_verdict,
                'confidence_tier': 'High' if abs(final_bin_a - 0.5) > 0.18 else ('Medium' if abs(final_bin_a - 0.5) > 0.08 else 'Tight Clash')
            },
            'score_prediction': {
                'projected_home_xg': round(xg_a, 2),
                'projected_away_xg': round(xg_b, 2),
                'most_likely_score': top_score['score'],
                'top_scores': score_matrix[:6],
                'over_2_5_prob': round(sum([s['prob'] for s in score_matrix if s['team_a_goals'] + s['team_b_goals'] > 2]), 1)
            },
            'goalscorers': {
                'home': scorers_a[:6],
                'away': scorers_b[:6]
            },
            'xai_attributions': xai_breakdown,
            'home_stats': stats_a,
            'away_stats': stats_b,
            'tactical_metrics': [
                {
                    'label': 'Starting XI Overall Quality (Effective)',
                    'home': round(stats_a['starter_overall_mean'], 1),
                    'away': round(stats_b['starter_overall_mean'], 1),
                    'advantage': 'home' if stats_a['starter_overall_mean'] > stats_b['starter_overall_mean'] else 'away'
                },
                {
                    'label': 'Goalkeeper Effective Rating',
                    'home': round(stats_a['overall_mean_GK'], 1),
                    'away': round(stats_b['overall_mean_GK'], 1),
                    'advantage': 'home' if stats_a['overall_mean_GK'] > stats_b['overall_mean_GK'] else 'away'
                },
                {
                    'label': 'Attacking Line Power',
                    'home': round(stats_a['overall_mean_ATT'], 1),
                    'away': round(stats_b['overall_mean_ATT'], 1),
                    'advantage': 'home' if stats_a['overall_mean_ATT'] > stats_b['overall_mean_ATT'] else 'away'
                },
                {
                    'label': 'Midfield Playmaking & Control',
                    'home': round(stats_a['overall_mean_MID'], 1),
                    'away': round(stats_b['overall_mean_MID'], 1),
                    'advantage': 'home' if stats_a['overall_mean_MID'] > stats_b['overall_mean_MID'] else 'away'
                },
                {
                    'label': 'Defensive Line Strength',
                    'home': round(stats_a['overall_mean_DEF'], 1),
                    'away': round(stats_b['overall_mean_DEF'], 1),
                    'advantage': 'home' if stats_a['overall_mean_DEF'] > stats_b['overall_mean_DEF'] else 'away'
                },
                {
                    'label': 'Aerial Clash: Attack vs Opp. Defense (cm)',
                    'home': round(stats_a['height_mean_ATT'], 1),
                    'away': round(stats_b['height_mean_DEF'], 1),
                    'advantage': 'home' if stats_a['height_mean_ATT'] > stats_b['height_mean_DEF'] else 'away'
                },
                {
                    'label': 'Squad Physical Prime Factor (Age Peak)',
                    'home': round(stats_a['starter_prime_mean'] * 100, 1),
                    'away': round(stats_b['starter_prime_mean'] * 100, 1),
                    'advantage': 'home' if stats_a['starter_prime_mean'] > stats_b['starter_prime_mean'] else 'away'
                },
                {
                    'label': 'Bench / Substitute Depth',
                    'home': round(stats_a['sub_overall_mean'], 1),
                    'away': round(stats_b['sub_overall_mean'], 1),
                    'advantage': 'home' if stats_a['sub_overall_mean'] > stats_b['sub_overall_mean'] else 'away'
                }
            ]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Advanced 4-Tier Match Predictor with OOP Penalty running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
