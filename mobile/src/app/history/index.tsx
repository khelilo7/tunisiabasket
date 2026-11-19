import { router } from 'expo-router';
import { Pressable, View } from 'react-native';

import { Card, ErrorView, Grid, Header, Loading, Row, Screen, Section, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { seasonLbl } from '@/lib/format';
import { C } from '@/theme';

type Idx = { champions: { season: string; champion: string; champion_code?: string | null; final?: { runner_up: string; score: string } }[]; seasons: { season: string; champion: string; champion_code?: string; runner_up?: string; score?: string; boxes: number }[] };

export default function History() {
  const { t } = useApp();
  const { data, error, refresh } = useApi<Idx>('/api/history');
  const header = <Header />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const have = new Set(data.seasons.map(s => s.season));
  return (
    <Screen header={header}>
      <Txt v="h1">{t('history')}</Txt>
      <Section title={`${t('season')}s`} style={{ marginTop: 10 }}>
        <Grid>
          {data.seasons.map(s => (
            <Card key={s.season} onPress={() => router.push(`/history/${s.season}`)}>
              <Row style={{ gap: 12 }}>
                <TeamLogo code={s.champion_code} size={44} />
                <View style={{ flex: 1 }}>
                  <Txt v="num" style={{ fontSize: 20 }}>{seasonLbl(s.season)}</Txt>
                  <Txt v="sub" c={C.txt} numberOfLines={1}>🏆 {s.champion}</Txt>
                  {s.runner_up ? <Txt v="small" numberOfLines={1}>{s.runner_up}{s.score ? ` · ${s.score}` : ''}</Txt> : null}
                </View>
                {s.boxes ? <Txt v="small" c={C.orange}>{s.boxes} 📋</Txt> : null}
              </Row>
            </Card>
          ))}
        </Grid>
      </Section>
      <Section title={t('champions')}>
        <Card padded={false}>
          {data.champions.slice().reverse().map((c, i) => (
            <Pressable key={c.season} disabled={!have.has(c.season)} onPress={() => router.push(`/history/${c.season}`)}>
              <Row style={{ paddingHorizontal: 14, paddingVertical: 10, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                <Txt v="sub" c={have.has(c.season) ? C.orange : C.sub} style={{ width: 82 }}>{seasonLbl(c.season)}</Txt>
                <Txt v="sub" c={C.txt} style={{ flex: 1, fontWeight: '600' }} numberOfLines={1}>{c.champion}</Txt>
                {c.final ? <Txt v="small">{c.final.score}</Txt> : null}
              </Row>
            </Pressable>
          ))}
        </Card>
      </Section>
    </Screen>
  );
}
