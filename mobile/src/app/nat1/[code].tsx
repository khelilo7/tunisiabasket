import { useLocalSearchParams } from 'expo-router';
import { View } from 'react-native';

import { N1, TeamGameRow } from '@/components/nat1';
import { Card, ErrorView, Header, Loading, Row, Screen, Section, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { C, F } from '@/theme';

// A National One club: its line in the table and every game of its season (results, and the games still to play). The league has no box scores, only results.
export default function Nat1Team() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const { t, lang } = useApp();
  const { data, error, refresh } = useApi<N1>('/api/nat1');
  const header = <Header />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const row = data.standings.find(r => r.code === code);
  const games = data.matchdays.flatMap(m => m.games.filter(g => g.home === code || g.away === code).map(g => ({ ...g, md: m.matchday, date: g.date || m.date })));
  const done = games.filter(g => g.home_score != null);
  const todo = games.filter(g => g.home_score == null);
  const fr = lang === 'fr';
  return (
    <Screen header={header}>
      <View style={{ alignItems: 'center', gap: 8 }}>
        <TeamLogo code={String(code)} size={96} />
        <Txt style={{ fontFamily: F.display, fontSize: 32, color: C.txt, textAlign: 'center' }}>{(data.teams[String(code)] || String(code)).toUpperCase()}</Txt>
        <Txt v="small">{t('nat1')} · {data.season.replace('-', '/')}</Txt>
      </View>
      {row ? (
        <Card style={{ marginTop: 16 }}>
          <Row style={{ justifyContent: 'space-around' }}>
            {([[t('rank'), row.rank], [t('record'), `${row.w}-${row.l}`], ['PTS', row.pts], ['+/-', (row.diff > 0 ? '+' : '') + row.diff]] as const).map(([l, v]) => (
              <View key={l} style={{ alignItems: 'center' }}><Txt v="numL" c={l === t('rank') ? C.orange : C.txt}>{v}</Txt><Txt v="label">{l}</Txt></View>
            ))}
          </Row>
        </Card>
      ) : null}
      <Section title={t('results')}>
        {done.length ? <Card padded={false}>{done.slice().reverse().map((g, i) => <TeamGameRow key={i} g={g} md={g.md} code={String(code)} first={!i} />)}</Card>
          : <Card><Txt v="sub">{fr ? 'Pas encore de résultat' : 'No result yet'}</Txt></Card>}
      </Section>
      {todo.length ? (
        <Section title={t('upcoming')}>
          <Card padded={false}>{todo.map((g, i) => <TeamGameRow key={i} g={g} md={g.md} code={String(code)} first={!i} />)}</Card>
        </Section>
      ) : null}
      <Txt v="small" style={{ marginTop: 10 }}>{fr ? 'Nationale 1 : résultats seulement (pas de feuille de match).' : 'National One: results only (no box scores).'}</Txt>
    </Screen>
  );
}
