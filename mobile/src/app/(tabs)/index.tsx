import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, ScrollView, View } from 'react-native';

import { FixtureCard, GameCard } from '@/components/games';
import { News, NewsCard } from '@/components/news';
import { Avatar, Card, Grid, HeroCard, Loading, Row, Section, Screen, tap, TeamLogo, Txt, useLayout } from '@/components/ui';
import { useApi, usePhotos } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, one, seasonLbl, titleCase } from '@/lib/format';
import { GameSummary, Leader, Matchday, Standing } from '@/lib/types';
import { C, F, GRAD } from '@/theme';

type Home = { recent: GameSummary[]; standings: Standing[]; phase_mvp?: { phase: number; winner?: Mvp; leader?: Mvp; vote_leader?: Mvp; voting_open?: boolean; current?: Mvp } };
type Mvp = { id: string; name: string; team: string; photo?: string; pts: number; reb: number; ast: number; pir: number; gp?: number };
type Plan = { banner?: { mode: string; matchday: number; date: string; games: Matchday['games'] }; matchdays: Matchday[]; teams: Record<string, string> };
type Overview = { season: string; leaders: Leader[] };

export default function HomeScreen() {
  const { t, lang, fav } = useApp();
  const home = useApi<Home>('/api/home');
  const plan = useApi<Plan>('/api/planning');
  const ov = useApi<Overview>('/api/overview');
  const news = useApi<{ items: News[] }>('/api/news?limit=3');
  const { tablet } = useLayout();
  const photos = usePhotos();
  const refresh = () => { home.refresh(); plan.refresh(); ov.refresh(); news.refresh(); };

  const next = plan.data?.matchdays.find(m => m.games.some(g => !g.played));
  const favRow = fav ? home.data?.standings.find(s => s.code === fav) : undefined;
  const mvp = home.data?.phase_mvp?.winner || home.data?.phase_mvp?.current || home.data?.phase_mvp?.leader;

  return (
    <Screen onRefresh={refresh} refreshing={home.refreshing}>
      {/* header */}
      <Row style={{ gap: 12, marginBottom: 18 }}>
        <Image source={require('../../../assets/logo.png')} style={{ width: 44, height: 44 }} />
        <View style={{ flex: 1 }}>
          <Txt style={{ fontFamily: F.display, fontSize: 24, letterSpacing: 0.5 }}>TUNISIA <Txt style={{ fontFamily: F.display, fontSize: 24, color: C.red }}>BASKET</Txt></Txt>
          <Txt v="small">{t('proA')} · {ov.data ? seasonLbl(ov.data.season) : '…'}</Txt>
        </View>
        {fav ? (
          <Pressable onPress={() => { tap(); router.push(`/team/${fav}`); }} hitSlop={8} accessibilityLabel={t('favorite')}
            style={{ padding: 2, borderRadius: 22, borderWidth: 1.5, borderColor: 'rgba(255,138,31,0.55)' }}>
            <TeamLogo code={fav} size={36} />
          </Pressable>
        ) : null}
      </Row>

      {/* the two places the tab bar does not lead to */}
      <Row style={{ gap: 10 }}>
        {[
          { k: 'records', label: t('records'), icon: 'ribbon' as const, go: () => router.push('/records') },
          { k: 'history', label: t('history'), icon: 'time' as const, go: () => router.push('/history') },
        ].map(x => (
          <Pressable key={x.k} onPress={() => { tap(); x.go(); }} style={({ pressed }) => ({ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 14, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, opacity: pressed ? 0.7 : 1 })}>
            <Ionicons name={x.icon} size={18} color={C.amber} />
            <Txt v="sub" c={C.txt} style={{ fontWeight: '700', flex: 1 }} numberOfLines={1}>{x.label}</Txt>
            <Ionicons name="chevron-forward" size={14} color={C.mut} />
          </Pressable>
        ))}
      </Row>

      {home.loading && plan.loading ? <Loading /> : null}

      {/* my club: one quiet line */}
      {favRow ? (
        <Pressable onPress={() => { tap(); router.push(`/team/${favRow.code}`); }} style={({ pressed }) => ({ marginTop: 14, opacity: pressed ? 0.7 : 1 })}>
          <Row style={{ gap: 10, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,138,31,0.25)', backgroundColor: 'rgba(255,138,31,0.06)' }}>
            <Ionicons name="star" size={13} color={C.orange} />
            <Txt v="sub" c={C.txt} style={{ flex: 1, fontWeight: '600' }} numberOfLines={1}>{favRow.name}</Txt>
            <Txt v="small">{favRow.rank}{lang === 'fr' ? (favRow.rank === 1 ? 'er' : 'e') : ordinal(favRow.rank)} · {favRow.w}-{favRow.l}</Txt>
            <Ionicons name="chevron-forward" size={14} color={C.mut} />
          </Row>
        </Pressable>
      ) : null}

      {/* coming up */}
      {next ? (
        <Section title={`${t('matchday')} ${next.matchday}`} action={t('seeAll')} onAction={() => router.navigate('/scores')}>
          <Txt v="small" style={{ marginTop: -6, marginBottom: 10 }}>{t('upcoming')} · {dayLabel(next.date, lang, { weekday: 'long', day: 'numeric', month: 'long' })}</Txt>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
            {next.games.filter(g => !g.played).map(g => (
              <View key={g.key} style={{ width: tablet ? 340 : 290 }}><FixtureCard g={g} date={next.date} names={plan.data?.teams || {}} /></View>
            ))}
          </ScrollView>
        </Section>
      ) : null}

      {/* MVP */}
      {mvp ? (
        <View style={{ marginTop: 24 }}>
          <HeroCard colors={GRAD.hero} onPress={() => router.push(`/player/${mvp.id}`)}>
            <Row style={{ gap: 14 }}>
              <View style={{ flex: 1 }}>
                <Txt style={{ fontFamily: F.display, fontSize: 30, lineHeight: 30, color: '#fff' }}>{home.data?.phase_mvp?.winner ? 'MVP' : t('mvpRace').toUpperCase()}</Txt>
                <Txt style={{ fontFamily: F.display, fontSize: 18, color: 'rgba(255,255,255,0.85)' }}>PHASE {home.data?.phase_mvp?.phase}</Txt>
                <Txt v="h3" c="#fff" style={{ marginTop: 10, fontSize: 18 }}>{titleCase(mvp.name)}</Txt>
                <Row style={{ gap: 16, marginTop: 8 }}>
                  {([['pts', mvp.pts], ['reb', mvp.reb], ['ast', mvp.ast], ['pir', mvp.pir]] as const).map(([k, v]) => (
                    <View key={k}><Txt v="label" c="rgba(255,255,255,0.75)">{t(k)}</Txt><Txt style={{ fontFamily: F.display, fontSize: 30, color: '#fff' }}>{one(v)}</Txt></View>
                  ))}
                </Row>
              </View>
              <Avatar photo={mvp.photo} name={mvp.name} size={tablet ? 140 : 108} team={mvp.team} />
            </Row>
          </HeroCard>
        </View>
      ) : null}

      {/* news */}
      {news.data?.items?.length ? (
        <Section title={lang === 'fr' ? 'Actualités' : 'News'} action={t('seeAll')} onAction={() => router.push('/news')}>
          <Grid>{news.data.items.map(n => <NewsCard key={n.id} n={n} />)}</Grid>
        </Section>
      ) : null}

      {/* latest */}
      {home.data?.recent?.length ? (
        <Section title={t('latest')} action={t('seeAll')} onAction={() => router.navigate('/scores')}>
          <Grid>{home.data.recent.slice(0, tablet ? 6 : 4).map((g, i) => <GameCard key={(g.id || '') + i} g={g} />)}</Grid>
        </Section>
      ) : null}

      {/* leaders */}
      {ov.data?.leaders ? (
        <Section title={t('leaders')} action={t('seeAll')} onAction={() => router.navigate('/players')}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
            {ov.data.leaders.filter(l => ['pts', 'reb', 'ast', 'pir'].includes(l.key)).map(l => {
              const top = l.top[0];
              return (
                <Card key={l.key} onPress={() => router.push(`/player/${top.id}`)} style={{ width: 210 }}>
                  <Txt v="label">{t(l.key as 'pts')} · {t('perGame')}</Txt>
                  <Row style={{ gap: 10, marginTop: 10 }}>
                    <Avatar photo={photos[top.id]} name={top.name} size={46} team={top.team} />
                    <View style={{ flex: 1 }}>
                      <Txt v="h3" numberOfLines={1}>{titleCase(top.name)}</Txt>
                      <Txt v="numL" c={C.orange}>{one(top.value)}</Txt>
                    </View>
                  </Row>
                  {l.top.slice(1, 3).map((x, i) => (
                    <Row key={x.id} style={{ marginTop: 6 }}><Txt v="small" style={{ width: 16 }}>{i + 2}</Txt><Txt v="small" c={C.sub} style={{ flex: 1 }} numberOfLines={1}>{titleCase(x.name)}</Txt><Txt v="small" c={C.txt}>{one(x.value)}</Txt></Row>
                  ))}
                </Card>
              );
            })}
          </ScrollView>
        </Section>
      ) : null}

      {/* table */}
      {home.data?.standings?.length ? (
        <Section title={t('standings')} action={t('seeAll')} onAction={() => router.navigate('/standings')}>
          <Card padded={false}>
            {home.data.standings.slice(0, 6).map((s, i) => (
              <Pressable key={s.code} onPress={() => router.push(`/team/${s.code}`)}>
                <Row style={{ paddingHorizontal: 16, paddingVertical: 11, gap: 12, borderTopWidth: i ? 1 : 0, borderColor: C.line, backgroundColor: s.code === fav ? 'rgba(255,138,31,0.08)' : undefined }}>
                  <Txt v="num" c={i < 4 ? C.orange : C.sub} style={{ width: 22, fontSize: 18 }}>{s.rank}</Txt>
                  <TeamLogo code={s.code} size={30} />
                  <Txt v="h3" style={{ flex: 1, fontWeight: '600' }} numberOfLines={1}>{s.name}</Txt>
                  <Txt v="sub" style={{ width: 46, textAlign: 'right' }}>{s.w}-{s.l}</Txt>
                  <Txt v="num" style={{ width: 34, textAlign: 'right', fontSize: 18 }}>{s.pts}</Txt>
                </Row>
              </Pressable>
            ))}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}

const ordinal = (n: number) => (n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th');
