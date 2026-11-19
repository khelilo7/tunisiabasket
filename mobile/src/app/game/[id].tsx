import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { Avatar, Card, CompareBar, ErrorView, Header, HeroCard, Loading, Row, Screen, Segmented, TeamLogo, Txt, useLayout } from '@/components/ui';
import { useApi, usePhotos } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, pct, titleCase } from '@/lib/format';
import { BoxLine, Game } from '@/lib/types';
import { C, F, GRAD } from '@/theme';

type Tab = 'summary' | 'box' | 'compare';

export default function GameScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, lang } = useApp();
  const { data: g, error, refresh } = useApi<Game>(`/api/games/${id}`);
  const [tab, setTab] = useState<Tab>('summary');
  const [side, setSide] = useState(0);
  const { tablet } = useLayout();
  const photos = usePhotos();

  const header = <Header title={g ? `${g.teams[0].code} – ${g.teams[1].code}` : ''} />;
  if (!g) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const [a, b] = g.teams;
  const aw = a.points > b.points;
  const lines = (code: string) => { const l = g.lineups?.[code]; return l ? [...l.starters, ...l.bench] : []; };
  const sum = (code: string, k: keyof BoxLine) => lines(code).reduce((s, p) => s + (Number(p[k]) || 0), 0);
  const tops = (code: string) => lines(code).slice().sort((x, y) => y.pts - x.pts).slice(0, 3);

  return (
    <Screen header={header}>
      {/* scoreboard */}
      <Card style={{ paddingVertical: 22 }}>
        <Txt v="label" style={{ textAlign: 'center' }}>{g.matchday ? `${t('matchday')} ${g.matchday.replace(/^J/, '')} · ` : ''}{g.date_approx ? '' : dayLabel(g.date, lang, { weekday: 'long', day: 'numeric', month: 'long' })}</Txt>
        <Row style={{ marginTop: 16 }}>
          <Pressable style={{ flex: 1, alignItems: 'center', gap: 8 }} onPress={() => router.push(`/team/${a.code}`)}>
            <TeamLogo code={a.code} size={tablet ? 84 : 66} />
            <Txt v="sub" c={aw ? C.txt : C.mut} style={{ fontWeight: '700', textAlign: 'center' }} numberOfLines={2}>{a.name}</Txt>
          </Pressable>
          <View style={{ alignItems: 'center' }}>
            <Row style={{ gap: 10 }}>
              <Txt style={{ fontFamily: F.display, fontSize: tablet ? 64 : 52, color: aw ? C.txt : C.mut }}>{a.points}</Txt>
              <Txt v="h2" c={C.mut}>:</Txt>
              <Txt style={{ fontFamily: F.display, fontSize: tablet ? 64 : 52, color: !aw ? C.txt : C.mut }}>{b.points}</Txt>
            </Row>
            <View style={{ backgroundColor: C.glass, borderRadius: 99, paddingHorizontal: 12, paddingVertical: 4, borderWidth: 1, borderColor: C.line }}><Txt v="small" c={C.sub} style={{ fontWeight: '700' }}>{t('final')}</Txt></View>
          </View>
          <Pressable style={{ flex: 1, alignItems: 'center', gap: 8 }} onPress={() => router.push(`/team/${b.code}`)}>
            <TeamLogo code={b.code} size={tablet ? 84 : 66} />
            <Txt v="sub" c={!aw ? C.txt : C.mut} style={{ fontWeight: '700', textAlign: 'center' }} numberOfLines={2}>{b.name}</Txt>
          </Pressable>
        </Row>
      </Card>

      {/* records set in this game */}
      {g.records?.length ? (
        <Card style={{ marginTop: 12, borderColor: 'rgba(255,181,71,0.5)' }}>
          <Row style={{ gap: 8, marginBottom: 6 }}><Ionicons name="ribbon" size={18} color={C.amber} /><Txt v="label" c={C.amber}>{t('records')}</Txt></Row>
          {g.records.map(r => (
            <Txt key={r.key} v="sub" style={{ marginTop: 4 }}>{r.equal ? t('equalsRecord') : t('newRecord')} · <Txt v="sub" c={C.txt} style={{ fontWeight: '700' }}>{r.value}</Txt> — {titleCase(r.who)} <Txt v="small">({t('previous')} {r.previous})</Txt></Txt>
          ))}
        </Card>
      ) : null}

      {/* MVP */}
      {g.mvp ? (
        <View style={{ marginTop: 12 }}>
          <HeroCard colors={GRAD.hero} onPress={() => router.push(`/player/${g.mvp!.player_id}`)} style={{ padding: 18 }}>
            <Row style={{ gap: 14 }}>
              <View style={{ flex: 1 }}>
                <Txt style={{ fontFamily: F.display, fontSize: 26, lineHeight: 26, color: '#fff' }}>MVP {lang === 'fr' ? 'DU MATCH' : 'OF THE GAME'}</Txt>
                <Txt v="h3" c="#fff" style={{ marginTop: 6 }}>{titleCase(g.mvp.name)}</Txt>
                <Row style={{ gap: 18, marginTop: 6 }}>
                  {([['pts', g.mvp.pts], ['reb', g.mvp.reb], ['ast', g.mvp.ast], ['pir', g.mvp.pir]] as const).map(([k, v]) => (
                    <View key={k}><Txt v="label" c="rgba(255,255,255,0.75)">{t(k)}</Txt><Txt style={{ fontFamily: F.display, fontSize: 30, color: '#fff' }}>{v}</Txt></View>
                  ))}
                </Row>
              </View>
              <Avatar photo={photos[g.mvp.player_id]} name={g.mvp.name} size={74} team={g.mvp.team} />
            </Row>
          </HeroCard>
        </View>
      ) : null}

      <View style={{ marginTop: 18 }}>
        <Segmented<Tab> value={tab} onChange={setTab} items={[{ key: 'summary', label: t('summary') }, { key: 'box', label: t('boxScore') }, { key: 'compare', label: t('comparison') }]} />
      </View>

      {tab === 'summary' ? (
        <View style={{ marginTop: 14, gap: 12, flexDirection: tablet ? 'row' : 'column' }}>
          {[a, b].map(team => (
            <Card key={team.code} style={{ flex: 1 }}>
              <Row style={{ gap: 10, marginBottom: 10 }}><TeamLogo code={team.code} size={28} /><Txt v="h3">{team.name}</Txt></Row>
              <Txt v="label" style={{ marginBottom: 6 }}>{t('topPerformers')}</Txt>
              {tops(team.code).map(p => (
                <Pressable key={p.id || p.name} onPress={() => p.id && router.push(`/player/${p.id}`)}>
                  <Row style={{ paddingVertical: 8, gap: 10, borderTopWidth: 1, borderColor: C.line }}>
                    <Avatar photo={p.id ? photos[p.id] : undefined} name={p.name} size={36} />
                    <View style={{ flex: 1 }}>
                      <Txt v="sub" c={C.txt} style={{ fontWeight: '700' }} numberOfLines={1}>{titleCase(p.name)}</Txt>
                      <Txt v="small">#{p.number} · {Math.round(p.min)} min · {p.fgm}/{p.fga} {t('fg').toLowerCase()}</Txt>
                    </View>
                    <Stat v={p.pts} l={t('pts')} hi /><Stat v={p.reb} l={t('reb')} /><Stat v={p.ast} l={t('ast')} />
                  </Row>
                </Pressable>
              ))}
            </Card>
          ))}
        </View>
      ) : null}

      {tab === 'compare' ? (
        <Card style={{ marginTop: 14 }}>
          <Row style={{ justifyContent: 'space-between', marginBottom: 6 }}><TeamLogo code={a.code} size={30} /><Txt v="label">{t('comparison')}</Txt><TeamLogo code={b.code} size={30} /></Row>
          <CompareBar label={t('fg')} a={pctOf(sum(a.code, 'fgm'), sum(a.code, 'fga'))} b={pctOf(sum(b.code, 'fgm'), sum(b.code, 'fga'))} fmt={pct} />
          <CompareBar label={t('threes')} a={pctOf(sum(a.code, 'p3m'), sum(a.code, 'p3a'))} b={pctOf(sum(b.code, 'p3m'), sum(b.code, 'p3a'))} fmt={pct} />
          <CompareBar label={t('ft')} a={pctOf(sum(a.code, 'ftm'), sum(a.code, 'fta'))} b={pctOf(sum(b.code, 'ftm'), sum(b.code, 'fta'))} fmt={pct} />
          {(['reb', 'oreb', 'ast', 'stl', 'blk', 'tov'] as const).map(k => (
            <CompareBar key={k} label={k === 'oreb' ? 'OR' : t(k)} a={sum(a.code, k)} b={sum(b.code, k)} />
          ))}
          {a.extra && b.extra ? Object.keys(a.extra).filter(k => b.extra?.[k] != null).map(k => (
            <CompareBar key={k} label={EXTRA[lang][k] || k} a={a.extra![k]} b={b.extra![k]} />
          )) : null}
        </Card>
      ) : null}

      {tab === 'box' ? (
        <View style={{ marginTop: 14 }}>
          <Segmented<string> value={String(side)} onChange={v => setSide(Number(v))} items={[{ key: '0', label: a.code }, { key: '1', label: b.code }]} />
          <Box lines={g.lineups?.[g.teams[side].code]} />
        </View>
      ) : null}
    </Screen>
  );
}

const EXTRA: Record<string, Record<string, string>> = {
  en: { paint: 'Points in the paint', second: 'Second-chance points', fast: 'Fast-break points', tov_pts: 'Points off turnovers', bench: 'Bench points' },
  fr: { paint: 'Points dans la raquette', second: 'Points de seconde chance', fast: 'Points en contre-attaque', tov_pts: 'Points sur balles perdues', bench: 'Points du banc' },
};
const pctOf = (m: number, a: number) => (a ? (100 * m) / a : 0);

function Stat({ v, l, hi }: { v: number; l: string; hi?: boolean }) {
  return <View style={{ alignItems: 'center', width: 36 }}><Txt v="num" c={hi ? C.orange : C.txt} style={{ fontSize: 20 }}>{v}</Txt><Txt v="label" style={{ fontSize: 9 }}>{l}</Txt></View>;
}

const COLS: { k: keyof BoxLine | 'fg' | '3p' | 'ft'; l: string; w: number }[] = [
  { k: 'min', l: 'MIN', w: 40 }, { k: 'pts', l: 'PTS', w: 40 }, { k: 'reb', l: 'REB', w: 40 }, { k: 'ast', l: 'AST', w: 40 }, { k: 'stl', l: 'STL', w: 40 },
  { k: 'blk', l: 'BLK', w: 40 }, { k: 'tov', l: 'TO', w: 36 }, { k: 'fg', l: 'FG', w: 52 }, { k: '3p', l: '3P', w: 48 }, { k: 'ft', l: 'FT', w: 48 }, { k: 'pf', l: 'PF', w: 36 }, { k: 'pir', l: 'PIR', w: 40 },
];

function Box({ lines }: { lines?: { starters: BoxLine[]; bench: BoxLine[]; dnp: BoxLine[] } }) {
  const { t } = useApp();
  if (!lines) return null;
  const cell = (p: BoxLine, k: (typeof COLS)[number]['k']) => k === 'fg' ? `${p.fgm}/${p.fga}` : k === '3p' ? `${p.p3m}/${p.p3a}` : k === 'ft' ? `${p.ftm}/${p.fta}` : k === 'min' ? Math.round(p.min) : String(p[k] ?? '–');
  const rows = (list: BoxLine[], label: string) => (
    <>
      <Row style={{ backgroundColor: C.card2, paddingVertical: 6 }}><Txt v="label" style={{ width: 150, paddingLeft: 12 }}>{label}</Txt></Row>
      {list.map(p => (
        <Pressable key={p.id || p.name} onPress={() => p.id && router.push(`/player/${p.id}`)}>
          <Row style={{ paddingVertical: 9, borderTopWidth: 1, borderColor: C.line }}>
            <Txt v="sub" c={C.txt} numberOfLines={1} style={{ width: 150, paddingLeft: 12, fontWeight: '600' }}>{p.number} · {titleCase(p.name)}</Txt>
            {COLS.map(c => <Txt key={c.k} v="sub" c={c.k === 'pts' ? C.txt : C.sub} style={{ width: c.w, textAlign: 'center', fontWeight: c.k === 'pts' ? '800' : '400' }}>{cell(p, c.k)}</Txt>)}
          </Row>
        </Pressable>
      ))}
    </>
  );
  return (
    <Card padded={false} style={{ marginTop: 12 }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View>
          <Row style={{ paddingVertical: 10 }}>
            <Txt v="label" style={{ width: 150, paddingLeft: 12 }}>{t('players')}</Txt>
            {COLS.map(c => <Txt key={c.k} v="label" style={{ width: c.w, textAlign: 'center' }}>{c.l}</Txt>)}
          </Row>
          {rows(lines.starters, t('starters'))}
          {rows(lines.bench, t('bench'))}
        </View>
      </ScrollView>
    </Card>
  );
}
