import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, View } from 'react-native';

import { Card, ErrorView, Grid, Header, HeroCard, Loading, Row, Screen, Section, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { seasonLbl } from '@/lib/format';
import { C, F, GRAD } from '@/theme';

type TeamRef = { code?: string | null; name: string };
type Sec = { name: string; table: { rank: number; code?: string | null; name: string; j: number; w: number; l: number; pts?: number }[] | null; series: { round?: string; a: TeamRef; b: TeamRef; games: number[][]; wins?: number[]; aggregate?: number[]; box?: (string | null)[] }[]; games: unknown[] };
type View_ = { season: string; champion: string; champion_code?: string; runner_up?: string; final_score?: string; relegated?: string; format?: { en: string; fr: string; source: string }; sections: Sec[]; boxes: { id: string; date: string; a: string; b: string; as: number; bs: number }[] };

export default function SeasonScreen() {
  const { season } = useLocalSearchParams<{ season: string }>();
  const { t, lang } = useApp();
  const { data, error, refresh } = useApi<View_>(`/api/history/${season}`);
  const header = <Header title={`${t('history')} ${seasonLbl(String(season))}`} />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  return (
    <Screen header={header}>
      <HeroCard colors={GRAD.gold}>
        <Row style={{ gap: 14 }}>
          <TeamLogo code={data.champion_code} size={72} />
          <View style={{ flex: 1 }}>
            <Txt v="label" c="rgba(26,18,5,0.7)">{t('champions')} {seasonLbl(data.season)}</Txt>
            <Txt style={{ fontFamily: F.display, fontSize: 30, color: '#1A1205' }}>{data.champion?.toUpperCase()}</Txt>
            {data.runner_up ? <Txt v="sub" c="#2A1B05">{data.runner_up}{data.final_score ? ` · ${data.final_score}` : ''}</Txt> : null}
          </View>
        </Row>
      </HeroCard>
      {data.format ? <Card style={{ marginTop: 14 }}><Txt v="label" style={{ marginBottom: 6 }}>{t('format')}</Txt><Txt v="sub" c={C.txt}>{data.format[lang]}</Txt><Txt v="small" style={{ marginTop: 6 }}>{data.format.source}</Txt></Card> : null}

      {data.sections.map(s => (
        <Section key={s.name} title={s.name}>
          {s.table ? (
            <Card padded={false}>
              {s.table.map((r, i) => (
                <Row key={r.name} style={{ paddingHorizontal: 14, paddingVertical: 10, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                  <Txt v="num" c={i < 4 ? C.orange : C.sub} style={{ width: 24, fontSize: 17 }}>{r.rank}</Txt>
                  <TeamLogo code={r.code} size={26} />
                  <Txt v="sub" c={C.txt} style={{ flex: 1 }} numberOfLines={1}>{r.name}</Txt>
                  <Txt v="sub" style={{ width: 56, textAlign: 'right' }}>{r.w}-{r.l}</Txt>
                  {r.pts != null ? <Txt v="num" style={{ width: 34, textAlign: 'right', fontSize: 17 }}>{r.pts}</Txt> : null}
                </Row>
              ))}
            </Card>
          ) : null}
          {s.series.length ? (
            <View style={{ marginTop: s.table ? 12 : 0 }}>
              <Grid>
                {s.series.map((x, i) => {
                  const wa = x.wins ? x.wins[0] : x.games.filter(g => g[0] > g[1]).length, wb = x.wins ? x.wins[1] : x.games.filter(g => g[1] > g[0]).length;
                  return (
                    <Card key={i}>
                      <Txt v="label" style={{ marginBottom: 8 }}>{x.round}</Txt>
                      <Row style={{ gap: 8 }}>
                        <TeamLogo code={x.a.code} size={30} /><Txt v="sub" c={wa > wb ? C.txt : C.mut} style={{ flex: 1, fontWeight: '700' }} numberOfLines={1}>{x.a.name}</Txt>
                        <Txt v="num">{wa}–{wb}</Txt>
                        <Txt v="sub" c={wb > wa ? C.txt : C.mut} style={{ flex: 1, textAlign: 'right', fontWeight: '700' }} numberOfLines={1}>{x.b.name}</Txt><TeamLogo code={x.b.code} size={30} />
                      </Row>
                      <Row style={{ gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                        {x.games.map((g, j) => (
                          <Pressable key={j} disabled={!x.box?.[j]} onPress={() => router.push(`/game/${x.box?.[j]}`)}>
                            <Txt v="small" c={x.box?.[j] ? C.orange : C.sub}>{g[0]}–{g[1]}</Txt>
                          </Pressable>
                        ))}
                        {x.aggregate ? <Txt v="small">Σ {x.aggregate[0]}–{x.aggregate[1]}</Txt> : null}
                      </Row>
                    </Card>
                  );
                })}
              </Grid>
            </View>
          ) : null}
        </Section>
      ))}

      {data.boxes.length ? (
        <Section title={`${t('boxScore')} · ${data.boxes.length}`}>
          <Card padded={false}>
            {data.boxes.slice().reverse().map((b, i) => (
              <Pressable key={b.id} onPress={() => router.push(`/game/${b.id}`)}>
                <Row style={{ paddingHorizontal: 14, paddingVertical: 10, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                  <Txt v="small" style={{ width: 80 }}>{b.date}</Txt>
                  <TeamLogo code={b.a} size={24} /><Txt v="sub" c={C.txt}>{b.a}</Txt>
                  <Txt v="num" style={{ fontSize: 17, flex: 1, textAlign: 'center' }}>{b.as}–{b.bs}</Txt>
                  <Txt v="sub" c={C.txt}>{b.b}</Txt><TeamLogo code={b.b} size={24} />
                </Row>
              </Pressable>
            ))}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
