import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, View } from 'react-native';

import { Avatar, Card, ErrorView, Grid, Header, IconBtn, Loading, Row, Screen, Section, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, one, titleCase } from '@/lib/format';
import { Player, Standing } from '@/lib/types';
import { C, F } from '@/theme';

type Res = { game_id: string | null; matchday: number; opp: string; opp_name: string; pf: number; pa: number; won: boolean; home: boolean };
type Up = { date: string; matchday: number; opp: string; opp_name: string; home: boolean; time?: string | null };
type TeamV = { code: string; name: string; standing?: Standing; players: Player[]; results: Res[]; upcoming: Up[]; honours?: { league?: { n: number; last: string }; cup?: { n: number; last: string } } | null };

export default function TeamScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const { t, lang, fav, setFav } = useApp();
  const { data, error, refresh } = useApi<TeamV>(`/api/teams/${code}`);
  const isFav = fav === code;
  const header = <Header title="" right={<IconBtn name={isFav ? 'star' : 'star-outline'} active={isFav} onPress={() => setFav(isFav ? null : String(code))} />} />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const s = data.standing;
  const form = data.results.slice(-5);
  const roster = data.players.slice().sort((a, b) => b.pir - a.pir);

  return (
    <Screen header={header}>
      <View style={{ alignItems: 'center', gap: 10 }}>
        <TeamLogo code={data.code} size={110} />
        <Txt style={{ fontFamily: F.display, fontSize: 36, color: C.txt, textAlign: 'center' }}>{data.name.toUpperCase()}</Txt>
        {data.honours?.league ? <Txt v="small">🏆 {data.honours.league.n} × {lang === 'fr' ? 'champion de Tunisie' : 'Tunisian champion'}{data.honours.cup ? ` · ${data.honours.cup.n} × ${lang === 'fr' ? 'Coupe' : 'Cup'}` : ''}</Txt> : null}
      </View>

      {s ? (
        <Card style={{ marginTop: 18 }}>
          <Row style={{ justifyContent: 'space-around' }}>
            {([[t('rank'), s.rank], [t('record'), `${s.w}-${s.l}`], ['PTS', s.pts], ['+/-', (s.diff > 0 ? '+' : '') + s.diff]] as const).map(([l, v]) => (
              <View key={l} style={{ alignItems: 'center' }}><Txt v="numL" c={l === t('rank') ? C.orange : C.txt}>{v}</Txt><Txt v="label">{l}</Txt></View>
            ))}
          </Row>
          <Row style={{ gap: 6, justifyContent: 'center', marginTop: 14 }}>
            <Txt v="label" style={{ marginRight: 6 }}>{t('form')}</Txt>
            {form.map((r, i) => <View key={i} style={{ width: 26, height: 26, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: r.won ? 'rgba(62,207,142,0.18)' : 'rgba(255,93,108,0.18)' }}><Txt v="small" c={r.won ? C.good : C.bad} style={{ fontWeight: '800' }}>{r.won ? t('w') : t('l')}</Txt></View>)}
          </Row>
        </Card>
      ) : null}

      {data.upcoming?.length ? (
        <Section title={t('next')}>
          <Card>
            <Row style={{ gap: 12 }}>
              <TeamLogo code={data.upcoming[0].opp} size={48} />
              <View style={{ flex: 1 }}>
                <Txt v="h3">{data.upcoming[0].home ? t('vs') : '@'} {data.upcoming[0].opp_name}</Txt>
                <Txt v="small">{t('matchday')} {data.upcoming[0].matchday} · {dayLabel(data.upcoming[0].date, lang, { weekday: 'long', day: 'numeric', month: 'long' })}{data.upcoming[0].time ? ` · ${data.upcoming[0].time}` : ''}</Txt>
              </View>
              <Ionicons name={data.upcoming[0].home ? 'home' : 'airplane'} size={20} color={C.mut} />
            </Row>
          </Card>
        </Section>
      ) : null}

      <Section title={t('roster')}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
          {roster.map(p => (
            <Card key={p.id} onPress={() => router.push(`/player/${p.id}`)} style={{ width: 150, alignItems: 'center' }}>
              <Avatar photo={p.photo} name={p.name} size={72} />
              <Txt v="sub" c={C.txt} style={{ fontWeight: '700', marginTop: 8, textAlign: 'center' }} numberOfLines={2}>{titleCase(p.name)}</Txt>
              <Txt v="small">#{p.number}{p.pos ? ` · ${p.pos}` : ''}</Txt>
              <Row style={{ gap: 10, marginTop: 8 }}>
                <View style={{ alignItems: 'center' }}><Txt v="num" c={C.orange} style={{ fontSize: 20 }}>{one(p.pts)}</Txt><Txt v="label" style={{ fontSize: 9 }}>{t('pts')}</Txt></View>
                <View style={{ alignItems: 'center' }}><Txt v="num" style={{ fontSize: 20 }}>{one(p.reb)}</Txt><Txt v="label" style={{ fontSize: 9 }}>{t('reb')}</Txt></View>
                <View style={{ alignItems: 'center' }}><Txt v="num" style={{ fontSize: 20 }}>{one(p.ast)}</Txt><Txt v="label" style={{ fontSize: 9 }}>{t('ast')}</Txt></View>
              </Row>
            </Card>
          ))}
        </ScrollView>
      </Section>

      <Section title={t('results')}>
        <Grid>
          {data.results.slice().reverse().map((r, i) => (
            <Pressable key={i} disabled={!r.game_id} onPress={() => router.push(`/game/${r.game_id}`)}>
              <Card style={{ paddingVertical: 12 }}>
                <Row style={{ gap: 12 }}>
                  <Txt v="label" style={{ width: 30 }}>J{r.matchday}</Txt>
                  <TeamLogo code={r.opp} size={32} />
                  <Txt v="sub" c={C.txt} style={{ flex: 1 }} numberOfLines={1}>{r.home ? '' : '@ '}{r.opp_name}</Txt>
                  <Txt v="h3" c={r.won ? C.good : C.bad}>{r.won ? t('w') : t('l')}</Txt>
                  <Txt v="num" style={{ fontSize: 19 }}>{r.pf}-{r.pa}</Txt>
                  {r.game_id ? <Ionicons name="chevron-forward" size={16} color={C.mut} /> : <View style={{ width: 16 }} />}
                </Row>
              </Card>
            </Pressable>
          ))}
        </Grid>
      </Section>
    </Screen>
  );
}
