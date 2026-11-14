CREATE TABLE IF NOT EXISTS finished_matches (
  match_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  league TEXT,
  match_date TIMESTAMPTZ,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  home_goals INTEGER,
  away_goals INTEGER,
  status TEXT,
  raw_json JSONB,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS predictions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  p_home REAL,
  p_draw REAL,
  p_away REAL,
  xg_home REAL,
  xg_away REAL,
  predicted_score TEXT,
  verdict TEXT
);

CREATE TABLE IF NOT EXISTS players (
  id BIGINT PRIMARY KEY,
  name TEXT NOT NULL,
  full_name TEXT,
  tm_name TEXT,
  club TEXT,
  nat TEXT,
  pos TEXT,
  rating REAL,
  age REAL,
  height REAL,
  val REAL,
  goals_per_90 REAL,
  total_goals INTEGER,
  report_date DATE DEFAULT '2026-11-01',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE players ADD COLUMN IF NOT EXISTS report_date DATE DEFAULT '2026-11-01';

CREATE TABLE IF NOT EXISTS player_snapshots (
  player_id BIGINT NOT NULL,
  report_date DATE NOT NULL,
  club TEXT,
  rating REAL,
  val REAL,
  age REAL,
  goals_per_90 REAL,
  total_goals INTEGER,
  minutes_30d INTEGER,
  goals_30d INTEGER,
  assists_30d INTEGER,
  PRIMARY KEY (player_id, report_date)
);

CREATE TABLE IF NOT EXISTS presets (
  name TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  formation TEXT NOT NULL DEFAULT '4-3-3',
  starters JSONB NOT NULL,
  subs JSONB NOT NULL
);
