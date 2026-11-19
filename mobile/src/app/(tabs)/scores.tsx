import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, ScrollViewInstance, View } from 'react-native';

import { Card, Empty, ErrorView, Grid, Loading, Pill, Row, Screen, tap, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, titleCase } from '@/lib/format';
import { C, F, R } from '@/theme';

type SGame = { home: string; away: string; home_score: number | null; away_score: number | null; played: boolean; id: string | null; date: string | null; time: string | null; mvp?: { name: string; pts: number } | null };
type Sched = { season: string; teams: Record<string, string>; matchdays: { matchday: number; date: string | null; games: SGame[] }[]; current: number };

export default function Scores() {
  const { t, lang, fav } = useApp();
  const { data, error, refresh, refreshing } = useApi<Sched>('/api/schedule');
  const [md, setMd] = useState<number | null>(null);
  const strip = useRef<ScrollViewInstance>(null);
  const sel = md ?? data?.current ?? null;
  const day = data?.matchdays.find(m => m.matchday === sel);

  useEffect(() => {
    if (data && md == null) {
      const i = data.matchdays.findIndex(m => m.matchday === data.current);
      setTimeout(() => strip.current?.scrollTo({ x: Math.max(0, i * 68 - 120), animated: false }), 50);
    }
  }, [data, md]);

  const games = (day?.games || []).slice().sort((a, b) => Number(!!fav && (b.home === fav || b.away === fav)) - Number(!!fav && (a.home === fav || a.away === fav)));

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Txt v="h1">{t('scores')}</Txt>
      <Txt v="small" style={{ marginBottom: 14 }}>{t('proA')} · {data ? data.season.replace('-', '/') : ''}</Txt>

      {/* matchday strip */}
      <Card padded={false} style={{ paddingVertical: 12 }}>
        <ScrollView ref={strip} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 12 }}>
          {(data?.matchdays || []).map(m => {
            const on = m.matchday === sel;
            const done = m.games.every(g => g.played);
            return (
              <Pressable key={m.matchday} onPress={() => { tap(); setMd(m.matchday); }} style={{ width: 60, paddingVertical: 10, borderRadius: R.md, alignItems: 'center', backgroundColor: on ? C.orange : C.card2, borderWidth: 1, borderColor: on ? C.orange : C.line }}>
                <Txt v="label" c={on ? '#1A1205' : C.mut} style={{ fontSize: 10 }}>{m.date ? dayLabel(m.date, lang, { month: 'short' }) : ''}</Txt>
                <Txt style={{ fontFamily: F.display, fontSize: 24, color: on ? '#1A1205' : C.txt }}>J{m.matchday}</Txt>
                <View style={{ width: 6, height: 6, borderRadius: 3, marginTop: 2, backgroundColor: done ? (on ? '#1A1205' : C.good) : m.matchday === data?.current ? C.amber : 'transparent' }} />
              </Pressable>
            );
          })}
        </ScrollView>
      </Card>

      {error && !data ? <ErrorView onRetry={refresh} /> : null}
      {!data && !error ? <Loading /> : null}

      {day ? (
        <>
          <Row style={{ justifyContent: 'space-between', marginTop: 22, marginBottom: 12 }}>
            <Txt v="h2">{t('matchday')} {day.matchday}</Txt>
            {day.date ? <Txt v="sub">{dayLabel(day.date, lang, { weekday: 'long', day: 'numeric', month: 'long' })}</Txt> : null}
          </Row>
          {games.length ? (
            <Grid>{games.map(g => <ScoreRow key={g.home + g.away} g={g} names={data?.teams || {}} fav={fav} />)}</Grid>
          ) : <Empty text={t('empty')} />}
        </>
      ) : null}
    </Screen>
  );
}

function ScoreRow({ g, names, fav }: { g: SGame; names: Record<string, string>; fav: string | null }) {
  const { t, lang } = useApp();
  const hw = g.played && (g.home_score ?? 0) > (g.away_score ?? 0), aw = g.played && !hw;
  const mine = fav && (g.home === fav || g.away === fav);
  const side = (code: string, on: boolean, right?: boolean) => (
    <View style={{ flex: 1, alignItems: right ? 'flex-end' : 'flex-start', gap: 6 }}>
      <TeamLogo code={code} size={46} />
      <Txt v="sub" c={!g.played || on ? C.txt : C.mut} numberOfLines={1} style={{ fontWeight: on ? '700' : '500' }}>{(names[code] || code)}</Txt>
    </View>
  );
  return (
    <Card onPress={g.id ? () => router.push(`/game/${g.id}`) : undefined} glow={mine ? 'rgba(255,138,31,0.5)' : undefined}>
      <Row>
        {side(g.home, hw)}
        <View style={{ alignItems: 'center', minWidth: 110 }}>
          {g.played ? (
            <Row style={{ gap: 8 }}>
              <Txt v="numL" c={hw ? C.txt : C.mut}>{g.home_score}</Txt>
              <Txt v="small">:</Txt>
              <Txt v="numL" c={aw ? C.txt : C.mut}>{g.away_score}</Txt>
            </Row>
          ) : (
            <>
              <Txt v="num">{g.time || '––:––'}</Txt>
              <Txt v="small">{g.date ? dayLabel(g.date, lang) : t('tbd')}</Txt>
            </>
          )}
          <View style={{ marginTop: 6 }}>
            {g.played ? <Pill label={g.id ? t('boxScore') : t('final')} color={g.id ? 'rgba(255,138,31,0.16)' : C.glass} text={g.id ? C.orange : C.mut} icon={g.id ? 'stats-chart' : undefined} /> : null}
          </View>
        </View>
        {side(g.away, aw, true)}
      </Row>
      {g.mvp ? <Txt v="small" style={{ marginTop: 10, textAlign: 'center' }}>MVP · <Txt v="small" c={C.sub} style={{ fontWeight: '700' }}>{titleCase(g.mvp.name)}</Txt> · {g.mvp.pts} {t('pts')}</Txt> : null}
    </Card>
  );
}
