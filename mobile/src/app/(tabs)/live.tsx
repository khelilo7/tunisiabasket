import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Animated, Pressable, ScrollView, View } from 'react-native';

import { Avatar, Card, CompareBar, Empty, Row, Screen, Segmented, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, pct, titleCase } from '@/lib/format';
import { C, F } from '@/theme';

// The games an analyst is counting right now and has made public on the website (/api/live): score and clock, quarters, the five on the court,
// the last plays, the box score so far. It refreshes every 10 seconds while the screen is open.
type LP = { id: string; name: string; number: number; photo?: string | null; on: boolean; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number; pf: number; fgm: number; fga: number; p3m: number; p3a: number; ftm: number; fta: number; sec?: number; pm?: number; inj?: boolean; ej?: boolean };
type LT = { code: string; name: string; score: number; players: LP[]; totals: Record<string, number> };
type LG = { id: string; home: string; away: string; matchday?: number; source?: 'scoreboard'; final?: boolean; flow?: { lead: Record<string, number>; run: Record<string, number>; changes: number; ties: number }; clock?: { q: number; t: number } | null; teams: Record<string, LT>; quarters?: { periods: number; pts: Record<string, number[]> };
  plays: { q?: number; t?: number; team: string; name: string; number: number | null; text: string; pts: number }[] };
type Sched = { teams: Record<string, string>; current: number; matchdays: { matchday: number; date: string | null; games: { home: string; away: string; played: boolean; date: string | null; time: string | null }[] }[] };

// a game read automatically from the broadcast's scoreboard (source "scoreboard"): score, quarter, clock and the score changes, no players
const PLAY_FR: Record<string, string> = { 'free throw made': 'lancer franc réussi', '2-pointer made': 'tir à 2 pts réussi', '3-pointer made': 'tir à 3 pts réussi', 'score corrected': 'score corrigé' };
const clock = (c?: { q: number; t: number } | null) => (!c ? '' : `${c.q > 4 ? `OT${c.q - 4}` : `Q${c.q}`} · ${String(Math.floor(c.t / 60)).padStart(2, '0')}:${String(c.t % 60).padStart(2, '0')}`);

function LiveDot() {
  const [a] = useState(() => new Animated.Value(1));
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([Animated.timing(a, { toValue: 0.25, duration: 700, useNativeDriver: true }), Animated.timing(a, { toValue: 1, duration: 700, useNativeDriver: true })]));
    loop.start();
    return () => loop.stop();
  }, [a]);
  return <Animated.View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: C.bad, opacity: a }} />;
}

export default function Live() {
  const { t, lang } = useApp();
  const { data, refresh, refreshing } = useApi<{ games: LG[] }>('/api/live', { every: 10000 });
  const sched = useApi<Sched>('/api/schedule');
  const [sel, setSel] = useState<string | null>(null);
  const games = data?.games || [];
  const g = games.find(x => x.id === sel) || games[0];
  const fr = lang === 'fr';

  if (data && !games.length) {
    const md = sched.data?.matchdays.find(m => m.matchday === sched.data?.current);
    const next = md?.games.filter(x => !x.played) || [];
    return (
      <Screen onRefresh={refresh} refreshing={refreshing}>
        <Txt v="h1">{t('live')}</Txt>
        <Card style={{ alignItems: 'center', gap: 8, marginTop: 14, paddingVertical: 26 }}>
          <Ionicons name="radio-outline" size={34} color={C.mut} />
          <Txt v="h3">{fr ? 'Pas de match en direct' : 'No game live right now'}</Txt>
          <Txt v="small" style={{ textAlign: 'center' }}>{fr ? 'Quand un match est suivi en direct, son score et ses statistiques s’affichent ici.' : 'When a game is followed live, its score and stats show up here.'}</Txt>
        </Card>
        {next.length ? (
          <View style={{ marginTop: 22 }}>
            <Txt v="h2" style={{ marginBottom: 10 }}>{t('matchday')} {md?.matchday}</Txt>
            <Card padded={false}>
              {next.map((x, i) => (
                <Row key={x.home + x.away} style={{ paddingHorizontal: 14, paddingVertical: 12, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                  <TeamLogo code={x.home} size={28} /><Txt v="sub" c={C.txt} style={{ flex: 1 }} numberOfLines={1}>{sched.data?.teams[x.home] || x.home}</Txt>
                  <View style={{ alignItems: 'center', width: 70 }}><Txt v="num" style={{ fontSize: 17 }}>{x.time || '––:––'}</Txt><Txt v="small" style={{ fontSize: 10 }}>{x.date ? dayLabel(x.date, lang, { day: 'numeric', month: 'short' }) : ''}</Txt></View>
                  <Txt v="sub" c={C.txt} style={{ flex: 1, textAlign: 'right' }} numberOfLines={1}>{sched.data?.teams[x.away] || x.away}</Txt><TeamLogo code={x.away} size={28} />
                </Row>
              ))}
            </Card>
          </View>
        ) : null}
      </Screen>
    );
  }
  if (!g) return <Screen><Txt v="h1">{t('live')}</Txt><Empty text={t('loading')} /></Screen>;
  return <LiveGame g={g} games={games} setSel={setSel} onRefresh={refresh} refreshing={refreshing} />;
}

function LiveGame({ g, games, setSel, onRefresh, refreshing }: { g: LG; games: LG[]; setSel: (id: string) => void; onRefresh: () => void; refreshing: boolean }) {
  const { t, lang } = useApp();
  const [side, setSide] = useState(g.home);
  const [view, setView] = useState<'plays' | 'box' | 'compare'>('plays');
  const a = g.teams[g.home], b = g.teams[g.away];
  const fr = lang === 'fr';
  const q = g.quarters;
  return (
    <Screen onRefresh={onRefresh} refreshing={refreshing}>
      <Row style={{ gap: 10, marginBottom: 12 }}>
        <Txt v="h1">{t('live')}</Txt>
        {g.final
          ? <Row style={{ backgroundColor: C.card2, borderRadius: 99, paddingHorizontal: 10, paddingVertical: 4 }}><Txt v="small" c={C.txt} style={{ fontWeight: '800' }}>FINAL</Txt></Row>
          : <Row style={{ gap: 6, backgroundColor: 'rgba(255,93,108,0.14)', borderRadius: 99, paddingHorizontal: 10, paddingVertical: 4 }}><LiveDot /><Txt v="small" c={C.bad} style={{ fontWeight: '800' }}>{fr ? 'DIRECT' : 'LIVE'}</Txt></Row>}
      </Row>
      {games.length > 1 ? <GameStrip games={games} sel={g.id} setSel={setSel} fr={fr} /> : null}

      <Card style={{ paddingVertical: 20 }} glow="rgba(255,93,108,0.45)">
        <Txt v="label" style={{ textAlign: 'center' }}>{g.matchday ? `${t('matchday')} ${g.matchday}${g.final ? '' : ' · '}` : ''}{g.final ? '' : clock(g.clock)}</Txt>
        <Row style={{ marginTop: 12 }}>
          <View style={{ flex: 1, alignItems: 'center', gap: 6 }}><TeamLogo code={a.code} size={60} /><Txt v="sub" c={C.txt} style={{ fontWeight: '700', textAlign: 'center' }} numberOfLines={2}>{a.name}</Txt></View>
          <Row style={{ gap: 10 }}>
            <Txt style={{ fontFamily: F.display, fontSize: 52, color: a.score >= b.score ? C.txt : C.mut }}>{a.score}</Txt>
            <Txt v="h2" c={C.mut}>:</Txt>
            <Txt style={{ fontFamily: F.display, fontSize: 52, color: b.score >= a.score ? C.txt : C.mut }}>{b.score}</Txt>
          </Row>
          <View style={{ flex: 1, alignItems: 'center', gap: 6 }}><TeamLogo code={b.code} size={60} /><Txt v="sub" c={C.txt} style={{ fontWeight: '700', textAlign: 'center' }} numberOfLines={2}>{b.name}</Txt></View>
        </Row>
        {q ? (
          <View style={{ marginTop: 14, backgroundColor: C.card2, borderRadius: 12, padding: 8 }}>
            {[a, b].map(tm => (
              <Row key={tm.code} style={{ paddingVertical: 3 }}>
                <Txt v="small" c={C.txt} style={{ width: 52, fontWeight: '700' }}>{tm.code}</Txt>
                {(q.pts[tm.code] || []).map((v, i) => <Txt key={i} v="sub" style={{ flex: 1, textAlign: 'center' }}>{v}</Txt>)}
                <Txt v="sub" c={C.txt} style={{ width: 40, textAlign: 'right', fontWeight: '800' }}>{tm.score}</Txt>
              </Row>
            ))}
          </View>
        ) : null}
      </Card>

      {g.source === 'scoreboard' ? <ScoreTimeline g={g} fr={fr} /> : <AnalystBody g={g} side={side} setSide={setSide} view={view} setView={setView} />}
      <Txt v="small" style={{ marginTop: 12, textAlign: 'center' }} onPress={() => router.navigate('/scores')}>{g.source === 'scoreboard' ? (fr ? 'Score lu automatiquement sur la diffusion · mis à jour toutes les 10 secondes' : 'Score read automatically from the broadcast · updated every 10 seconds') : fr ? 'Mis à jour toutes les 10 secondes' : 'Updated every 10 seconds'}</Txt>
    </Screen>
  );
}

// several games at the same time: one small scoreboard per game in a strip (logos, score, quarter and clock, or FINAL); a tap opens that game below
function GameStrip({ games, sel, setSel, fr }: { games: LG[]; sel: string; setSel: (id: string) => void; fr: boolean }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
      {games.map(x => {
        const on = x.id === sel, a = x.teams[x.home], b = x.teams[x.away];
        return (
          <Pressable key={x.id} onPress={() => setSel(x.id)} accessibilityRole="button" accessibilityState={{ selected: on }}
            style={{ width: 132, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 14, backgroundColor: on ? 'rgba(255,93,108,0.12)' : C.card2, borderWidth: 1, borderColor: on ? C.bad : C.line }}>
            <Txt v="small" c={x.final ? C.txt : C.bad} style={{ fontSize: 10, fontWeight: '800', marginBottom: 4 }}>{x.final ? 'FINAL' : `● ${clock(x.clock) || (fr ? 'DIRECT' : 'LIVE')}`}</Txt>
            {[a, b].map(t => (
              <Row key={t.code} style={{ gap: 6, paddingVertical: 2 }}>
                <TeamLogo code={t.code} size={18} />
                <Txt v="small" c={C.txt} style={{ flex: 1, fontWeight: '700' }}>{t.code}</Txt>
                <Txt v="num" c={t.score >= (t === a ? b : a).score ? C.txt : C.mut} style={{ fontSize: 15 }}>{t.score}</Txt>
              </Row>
            ))}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function ScoreTimeline({ g, fr }: { g: LG; fr: boolean }) {
  const a = g.teams[g.home], b = g.teams[g.away], fl = g.flow;
  return (
    <>
      {fl && a.score + b.score > 0 ? (
        <Card style={{ marginTop: 12 }}>
          <Txt v="label" style={{ marginBottom: 8 }}>{fr ? 'Déroulement du match' : 'Game flow'}</Txt>
          <CompareBar label={fr ? 'Plus grand écart' : 'Biggest lead'} a={fl.lead[a.code] || 0} b={fl.lead[b.code] || 0} />
          <CompareBar label={fr ? 'Plus longue série' : 'Longest run'} a={fl.run[a.code] || 0} b={fl.run[b.code] || 0} />
          <Txt v="small" style={{ textAlign: 'center', marginTop: 6 }}>{fr ? 'Changements de leader' : 'Lead changes'} {fl.changes} · {fr ? 'Égalités' : 'Ties'} {fl.ties}</Txt>
        </Card>
      ) : null}
      <Txt v="h3" style={{ marginTop: 16, marginBottom: 8 }}>{fr ? 'Évolution du score' : 'Score timeline'}</Txt>
      <Card padded={false}>
        {g.plays.length ? g.plays.map((p, i) => (
          <Row key={i} style={{ paddingHorizontal: 12, paddingVertical: 9, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
            <Txt v="small" style={{ width: 70 }}>{p.q ? clock({ q: p.q, t: p.t || 0 }) : ''}</Txt>
            <TeamLogo code={p.team} size={22} />
            <Txt v="sub" c={C.txt} style={{ flex: 1 }} numberOfLines={1}>{p.team} · <Txt v="sub">{fr ? PLAY_FR[p.text] || p.text : p.text}</Txt></Txt>
            {p.pts ? <Txt v="num" c={C.good} style={{ fontSize: 16 }}>+{p.pts}</Txt> : null}
          </Row>
        )) : <Txt v="small" style={{ padding: 14 }}>{fr ? 'Pas encore de panier.' : 'No basket yet.'}</Txt>}
      </Card>
    </>
  );
}

function AnalystBody({ g, side, setSide, view, setView }: { g: LG; side: string; setSide: (s: string) => void; view: 'plays' | 'box' | 'compare'; setView: (v: 'plays' | 'box' | 'compare') => void }) {
  const { t, lang } = useApp();
  const a = g.teams[g.home], b = g.teams[g.away];
  const fr = lang === 'fr';
  return (
    <>
      {/* the fives on the court */}
      <Row style={{ gap: 10, marginTop: 12 }}>
        {[a, b].map(tm => (
          <Card key={tm.code} style={{ flex: 1, padding: 12 }}>
            <Txt v="label" style={{ marginBottom: 8 }}>{tm.code} · {fr ? 'sur le terrain' : 'on court'}</Txt>
            {tm.players.filter(p => p.on).map(p => (
              <Row key={p.id} style={{ gap: 6, paddingVertical: 3 }}>
                <Avatar photo={p.photo} name={p.name} size={26} />
                <Txt v="small" c={C.txt} style={{ flex: 1 }} numberOfLines={1}>{titleCase(p.name).split(' ').slice(-1)[0]}</Txt>
                <Txt v="small" c={C.orange} style={{ fontWeight: '800' }}>{p.pts}</Txt>
              </Row>
            ))}
          </Card>
        ))}
      </Row>

      <View style={{ marginTop: 14 }}>
        <Segmented<'plays' | 'box' | 'compare'> value={view} onChange={setView} items={[{ key: 'plays', label: fr ? 'Actions' : 'Plays' }, { key: 'box', label: t('boxScore') }, { key: 'compare', label: t('comparison') }]} />
      </View>

      {view === 'plays' ? (
        <Card padded={false} style={{ marginTop: 12 }}>
          {g.plays.map((p, i) => (
            <Row key={i} style={{ paddingHorizontal: 12, paddingVertical: 9, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
              <Txt v="small" style={{ width: 52 }}>{p.q ? clock({ q: p.q, t: p.t || 0 }) : ''}</Txt>
              <TeamLogo code={p.team} size={22} />
              <Txt v="sub" c={C.txt} style={{ flex: 1 }} numberOfLines={2}>{p.name ? `${p.number != null ? `#${p.number} ` : ''}${titleCase(p.name)} · ` : ''}<Txt v="sub">{p.text}</Txt></Txt>
              {p.pts ? <Txt v="num" c={C.good} style={{ fontSize: 16 }}>+{p.pts}</Txt> : null}
            </Row>
          ))}
        </Card>
      ) : null}

      {view === 'compare' ? (
        <Card style={{ marginTop: 12 }}>
          <CompareBar label={t('fg')} a={a.totals.fga ? (100 * a.totals.fgm) / a.totals.fga : 0} b={b.totals.fga ? (100 * b.totals.fgm) / b.totals.fga : 0} fmt={pct} />
          <CompareBar label={t('threes')} a={a.totals.p3a ? (100 * a.totals.p3m) / a.totals.p3a : 0} b={b.totals.p3a ? (100 * b.totals.p3m) / b.totals.p3a : 0} fmt={pct} />
          {(['reb', 'ast', 'stl', 'blk', 'tov', 'pf'] as const).map(k => <CompareBar key={k} label={k === 'pf' ? (fr ? 'Fautes' : 'Fouls') : t(k)} a={a.totals[k] || 0} b={b.totals[k] || 0} />)}
        </Card>
      ) : null}

      {view === 'box' ? (
        <View style={{ marginTop: 12 }}>
          <Segmented<string> value={side} onChange={setSide} items={[{ key: g.home, label: g.home }, { key: g.away, label: g.away }]} />
          <Card padded={false} style={{ marginTop: 10 }}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View>
                <Row style={{ paddingVertical: 9 }}>
                  <Txt v="label" style={{ width: 150, paddingLeft: 12 }}>{t('players')}</Txt>
                  {['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'FG', '3P', 'FT', 'PF'].map(h => <Txt key={h} v="label" style={{ width: h.length > 2 ? 46 : 40, textAlign: 'center' }}>{h}</Txt>)}
                </Row>
                {g.teams[side].players.map(p => (
                  <Row key={p.id} style={{ paddingVertical: 9, borderTopWidth: 1, borderColor: C.line, backgroundColor: p.on ? 'rgba(62,207,142,0.06)' : undefined }}>
                    <Txt v="sub" c={C.txt} numberOfLines={1} style={{ width: 150, paddingLeft: 12, fontWeight: p.on ? '700' : '500' }}>{p.number} · {titleCase(p.name)}{p.inj ? ' 🩹' : ''}{p.ej ? ' 🟥' : ''}</Txt>
                    {[p.sec != null ? Math.round(p.sec / 60) : '–', p.pts, p.reb, p.ast, p.stl, p.blk, p.tov, `${p.fgm}/${p.fga}`, `${p.p3m}/${p.p3a}`, `${p.ftm}/${p.fta}`, p.pf].map((v, i) => (
                      <Txt key={i} v="sub" c={i === 1 ? C.txt : C.sub} style={{ width: i >= 7 && i <= 9 ? 46 : i === 0 ? 46 : 40, textAlign: 'center', fontWeight: i === 1 ? '800' : '400' }}>{v}</Txt>
                    ))}
                  </Row>
                ))}
              </View>
            </ScrollView>
          </Card>
        </View>
      ) : null}
    </>
  );
}
