import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { Card, Chips, ErrorView, Grid, Header, Loading, Row, Screen, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, seasonLbl, titleCase } from '@/lib/format';
import { C } from '@/theme';

type Line = { value: number; player?: string; pid?: string; team?: string; opp?: string; score?: string; date?: string | null; season?: string; game_id?: string | null; club?: string; code?: string; from?: string; to?: string; gp?: number };
type Group = { key: string; label: string; top: Line[] };
type Recs = { player: Group[]; team: Group[]; season: Group[]; league: Group[]; coverage: { box_scores: Record<string, number> } };
type G = 'player' | 'team' | 'season' | 'league';

const FR: Record<string, string> = {
  Points: 'Points', Rebounds: 'Rebonds', Assists: 'Passes décisives', Steals: 'Interceptions', Blocks: 'Contres', 'Three-pointers made': 'Paniers à 3 points',
  'Free throws made': 'Lancers francs réussis', 'Efficiency (PIR)': 'Évaluation', 'Points scored by a team': 'Points marqués par une équipe', 'Biggest win': 'Plus large victoire',
  'Highest-scoring game': 'Match le plus prolifique', 'Three-pointers made by a team': 'Paniers à 3 pts d’une équipe', 'Assists by a team': 'Passes d’une équipe', 'Rebounds by a team': 'Rebonds d’une équipe',
  'Points per game': 'Points par match', 'Rebounds per game': 'Rebonds par match', 'Assists per game': 'Passes par match', 'Efficiency per game': 'Évaluation par match',
  'Most titles': 'Plus de titres', 'Most titles in a row': 'Plus de titres consécutifs', 'Unbeaten through a phase': 'Invaincu sur une phase',
};

export default function Records() {
  const { t, lang } = useApp();
  const { data, error, refresh } = useApi<Recs>('/api/records');
  const [g, setG] = useState<G>('player');
  const header = <Header />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const L = (s: string) => (lang === 'fr' ? FR[s] || s : s);
  const groups: { key: G; label: string }[] = [
    { key: 'player', label: lang === 'fr' ? 'Un match · joueur' : 'Game · player' }, { key: 'team', label: lang === 'fr' ? 'Un match · équipe' : 'Game · team' },
    { key: 'season', label: t('season') }, { key: 'league', label: lang === 'fr' ? 'Palmarès' : 'All time' },
  ];
  return (
    <Screen header={header}>
      <Txt v="h1">{t('records')}</Txt>
      <Txt v="small" style={{ marginBottom: 12 }}>{Object.entries(data.coverage.box_scores).map(([k, v]) => `${seasonLbl(k)} (${v})`).join(' · ')}</Txt>
      <Chips<G> items={groups} value={g} onChange={setG} />
      <View style={{ marginTop: 14 }}>
        <Grid>
          {data[g].map(r => {
            const top = r.top[0];
            return (
              <Card key={r.key}>
                <Txt v="label">{L(r.label)}</Txt>
                {top ? (
                  <Pressable disabled={!top.game_id} onPress={() => router.push(`/game/${top.game_id}`)}>
                    <Row style={{ gap: 12, marginTop: 10 }}>
                      <TeamLogo code={top.code || top.team} size={46} />
                      <View style={{ flex: 1 }}>
                        <Txt v="h3" numberOfLines={1}>{top.player ? titleCase(top.player) : top.club || top.team}</Txt>
                        <Txt v="small" numberOfLines={1}>{top.opp ? `${t('vs')} ${top.opp} ${top.score || ''} · ${top.date ? dayLabel(top.date, lang, { day: 'numeric', month: 'short', year: 'numeric' }) : seasonLbl(top.season || '')}` : top.from ? `${seasonLbl(top.from)} → ${seasonLbl(top.to || '')}` : seasonLbl(top.season || '')}</Txt>
                      </View>
                      <Txt v="numXL" c={C.amber}>{top.value}</Txt>
                    </Row>
                  </Pressable>
                ) : null}
                {r.top.slice(1, 5).map((x, i) => (
                  <Row key={i} style={{ marginTop: 8, gap: 8 }}>
                    <Txt v="small" style={{ width: 16 }}>{i + 2}</Txt>
                    <Txt v="small" c={C.sub} style={{ flex: 1 }} numberOfLines={1}>{x.player ? titleCase(x.player) : x.club || x.team} {x.opp ? `· ${t('vs')} ${x.opp}` : ''} · {seasonLbl(x.season || x.from || '')}</Txt>
                    <Txt v="sub" c={C.txt} style={{ fontWeight: '700' }}>{x.value}</Txt>
                  </Row>
                ))}
              </Card>
            );
          })}
        </Grid>
      </View>
    </Screen>
  );
}
