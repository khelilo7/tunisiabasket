import { View } from 'react-native';

import { useApp } from '@/lib/app-state';
import { dayLabel } from '@/lib/format';
import { C } from '@/theme';
import { Row, TeamLogo, Txt } from './ui';

// National One (/api/nat1): results only, no box scores.
export type N1Game = { home: string; away: string; home_name: string; away_name: string; home_score: number | null; away_score: number | null; date: string | null; time?: string | null; projected?: boolean };
export type N1 = { season: string; teams: Record<string, string>; standings: { code: string; name: string; rank: number; j: number; w: number; l: number; pts: number; diff: number }[];
  matchdays: { matchday: number; date: string | null; played: boolean; games: N1Game[] }[]; official?: { published: string; source: string } | null };


export function GameRow({ g, md, code, first }: { g: N1Game; md: number; code?: string; first?: boolean }) {
  const { lang } = useApp();
  const played = g.home_score != null && g.away_score != null;
  const mine = code ? (g.home === code ? 'home' : 'away') : null;
  const won = played && mine ? (mine === 'home' ? g.home_score! > g.away_score! : g.away_score! > g.home_score!) : null;
  return (
    <Row style={{ paddingHorizontal: 12, paddingVertical: 11, gap: 8, borderTopWidth: first ? 0 : 1, borderColor: C.line }}>
      <View style={{ width: 40 }}><Txt v="label" style={{ fontSize: 10 }}>J{md}</Txt>{g.date ? <Txt v="small" style={{ fontSize: 10 }}>{dayLabel(g.date, lang, { day: 'numeric', month: 'short' })}</Txt> : null}{g.time ? <Txt v="small" style={{ fontSize: 10 }}>{g.time}</Txt> : null}</View>
      <TeamLogo code={g.home} size={26} />
      <Txt v="sub" c={C.txt} style={{ flex: 1, fontWeight: mine === 'home' ? '700' : '400' }} numberOfLines={1}>{g.home_name}</Txt>
      <View style={{ minWidth: 64, alignItems: 'center', borderRadius: 8, paddingVertical: 3, backgroundColor: won == null ? C.card2 : won ? 'rgba(62,207,142,0.16)' : 'rgba(255,93,108,0.16)' }}>
        <Txt v="num" c={won == null ? C.txt : won ? C.good : C.bad} style={{ fontSize: 16 }}>{played ? `${g.home_score}–${g.away_score}` : '–'}</Txt>
      </View>
      <Txt v="sub" c={C.txt} style={{ flex: 1, textAlign: 'right', fontWeight: mine === 'away' ? '700' : '400' }} numberOfLines={1}>{g.away_name}</Txt>
      <TeamLogo code={g.away} size={26} />
    </Row>
  );
}

// One game of a club's season, seen from that club: the opponent, home or away, and the score (green won, red lost).
export function TeamGameRow({ g, md, code, first }: { g: N1Game; md: number; code: string; first?: boolean }) {
  const { lang } = useApp();
  const home = g.home === code;
  const opp = home ? g.away : g.home, oppName = home ? g.away_name : g.home_name;
  const played = g.home_score != null && g.away_score != null;
  const us = home ? g.home_score : g.away_score, them = home ? g.away_score : g.home_score;
  const won = played ? us! > them! : null;
  return (
    <Row style={{ paddingHorizontal: 12, paddingVertical: 11, gap: 10, borderTopWidth: first ? 0 : 1, borderColor: C.line }}>
      <View style={{ width: 44 }}><Txt v="label" style={{ fontSize: 10 }}>J{md}</Txt>{g.date ? <Txt v="small" style={{ fontSize: 10 }}>{dayLabel(g.date, lang, { day: 'numeric', month: 'short' })}</Txt> : null}{g.time ? <Txt v="small" style={{ fontSize: 10 }}>{g.time}</Txt> : null}</View>
      <TeamLogo code={opp} size={30} />
      <Txt v="sub" c={C.txt} style={{ flex: 1 }} numberOfLines={1}><Txt v="small">{home ? (lang === 'fr' ? 'contre ' : 'vs ') : '@ '}</Txt>{oppName}</Txt>
      {played ? (
        <Row style={{ gap: 6 }}>
          <Txt v="h3" c={won ? C.good : C.bad} style={{ width: 16, textAlign: 'center' }}>{won ? (lang === 'fr' ? 'V' : 'W') : (lang === 'fr' ? 'D' : 'L')}</Txt>
          <Txt v="num" style={{ fontSize: 17 }}>{us}–{them}</Txt>
        </Row>
      ) : <Txt v="small" c={C.mut}>{g.projected ? (lang === 'fr' ? 'prévu' : 'planned') : ''}</Txt>}
    </Row>
  );
}
