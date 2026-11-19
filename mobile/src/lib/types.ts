// The shapes the website's API answers with (only the fields the app reads).
export type TeamScore = { code: string; name: string; points: number; won?: boolean };
export type GameSummary = { id: string | null; date: string; date_approx?: boolean; matchday?: string; teams: TeamScore[]; mvp?: { name: string; team: string; pts: number; reb: number; ast: number; pir: number; player_id: string } | null; partial?: boolean };
export type Standing = { code: string; name: string; rank: number; j: number; w: number; l: number; pts: number; diff: number; pf: number; pa: number };
export type Leader = { key: string; top: { id: string; name: string; team: string; value: number; gp: number; number: number; rating: number }[] };
export type Player = {
  id: string; name: string; team: string; number: number; pos?: string; photo?: string | null; gp: number; min: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number;
  pir: number; rating: number; fg_pct: number; p3_pct: number; ft_pct: number; fgm: number; fga: number; p3m: number; p3a: number; ftm: number; fta: number; oreb: number; dreb: number;
  totals?: Record<string, number>; log?: LogRow[]; bio?: { birth?: string; height?: number; weight?: number }; wins?: number; mvp_games?: number; team_rank?: number;
};
export type LogRow = { game_id: string; date: string; matchday?: string; opp: string; score: string; won: boolean; home?: boolean | null; min?: number; pts: number; reb: number; ast: number; pir: number; stl: number; blk: number };
export type BoxLine = { pid?: string; id?: string; name: string; number: number; starter?: boolean; dnp?: boolean; min: number; pts: number; reb: number; oreb: number; dreb: number; ast: number; stl: number; blk: number; tov: number; pf: number; fgm: number; fga: number; p3m: number; p3a: number; ftm: number; fta: number; pir: number; rating?: number; pos?: string; pm?: number | null };
export type GameTeam = TeamScore & { players: BoxLine[]; extra?: Record<string, number>; quarters?: number[] };
export type RecordHit = { key: string; label: string; value: number; who: string; team: string; previous: number; previous_who?: string; equal: boolean };
export type Game = { id: string; date: string; date_approx?: boolean; matchday?: string; competition?: string; teams: GameTeam[]; mvp?: GameSummary['mvp']; lineups: Record<string, { starters: BoxLine[]; bench: BoxLine[]; dnp: BoxLine[] }>; records?: RecordHit[]; quarters?: number[][] };
export type PlanGame = { home: string; away: string; home_score: number | null; away_score: number | null; played: boolean; time?: string | null; game_date?: string | null; key: string };
export type Matchday = { matchday: number; date: string; games: PlanGame[] };
