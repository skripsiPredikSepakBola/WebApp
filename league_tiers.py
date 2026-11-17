"""Single source of truth for competition strength tier prior (0.75-1.00).

Hand-set league-quality prior used identically by offline training, retrain.py,
and app.py. Unknown leagues fall back to 0.95 with known=False (caps confidence
at Low in inference).
"""

LEAGUE_TIER_MAP = {
    # Top 5 European leagues + UEFA Champions League (elite tier = 1.00)
    'GB1': 1.00, 'ES1': 1.00, 'L1': 1.00, 'IT1': 1.00, 'FR1': 1.00, 'CL': 1.00,
    # Major international tournaments & strong European/Americas tiers (0.85-0.95)
    'FIWC': 0.95, 'EURO': 0.95, 'COPA': 0.92, 'EL': 0.92, 'USC': 0.92,
    'PO1': 0.90, 'NL1': 0.90, 'BRA1': 0.90,
    'FAC': 0.90, 'CDR': 0.90, 'DFB': 0.90, 'CIT': 0.90,
    'GBCS': 0.90, 'SUC': 0.90, 'DFL': 0.90, 'FRCH': 0.90, 'SCI': 0.90,
    'UCOL': 0.88, 'ARG1': 0.88, 'BE1': 0.87, 'TR1': 0.87,
    'SC1': 0.85, 'MEX1': 0.85, 'MLS1': 0.85, 'COL1': 0.85,
    'RU1': 0.85, 'UKR1': 0.85, 'DK1': 0.85, 'A1': 0.85, 'C1': 0.85,
    'GR1': 0.85, 'NO1': 0.85, 'SE1': 0.85, 'PL1': 0.85, 'TS1': 0.85,
    'KR1': 0.85, 'RO1': 0.85, 'SER1': 0.85, 'AFAC': 0.85, 'AFCN': 0.85,
    'CLQ': 0.85, 'ELQ': 0.85, 'ECLQ': 0.85, 'KLUB': 0.85,
    'NLP': 0.85, 'RUP': 0.85, 'DKP': 0.85, 'GRP': 0.85, 'SFA': 0.85,
    'POCP': 0.85, 'UKRP': 0.85, 'BESC': 0.85, 'NLSC': 0.85, 'POSU': 0.85,
    'RUSS': 0.85, 'UKRS': 0.85, 'BPO4': 0.85, 'EJPL': 0.85, 'POBE': 0.85,
    'CGB': 0.85,
    # Asian & Southeast Asian (SEA) leagues (0.75-0.80)
    'SA1': 0.80, 'JAP1': 0.80, 'RSK1': 0.80, 'AUS1': 0.78,
    'THA1': 0.78, 'MYS1': 0.77, 'IN1L': 0.76, 'VIE1': 0.76, 'SIN1': 0.75,
}

# Confederation fallbacks for additional competitions tracked in Transfermarkt
CONFED_FALLBACK = {
    'asien': 0.78,
    'europa': 0.85,
    'amerika': 0.85,
    'fifa': 0.85,
}

UNKNOWN_TIER_FALLBACK = 0.95


def resolve_league_tier(comp_id, confederation=None):
    """Return (tier_value, is_known). Unknown competitions fall back to 0.95 with is_known=False."""
    cid = str(comp_id or '').strip()
    if cid in LEAGUE_TIER_MAP:
        return LEAGUE_TIER_MAP[cid], True
    if confederation:
        conf = str(confederation).strip().lower()
        if conf in CONFED_FALLBACK:
            return CONFED_FALLBACK[conf], True
    return UNKNOWN_TIER_FALLBACK, False
