import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { Card, ErrorView, Header, Loading, Pill, Row, Screen, Segmented, StatTile, TeamLogo, Txt, useLayout } from '@/components/ui';
import { asset, useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, one, pct, titleCase } from '@/lib/format';
import { Player } from '@/lib/types';
import { C, F, R } from '@/theme';

type Tab = 'overview' | 'log';
const TODAY = Date.now();
const POS: Record<string, string> = { PG: 'Meneur · PG', SG: 'Arrière · SG', SF: 'Ailier · SF', PF: 'Ailier fort · PF', C: 'Pivot · C' };

export default function PlayerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, lang } = useApp();
  const { data, error, refresh } = useApi<{ player: Player; rank?: number; of?: number }>(`/api/players/${id}`);
  const [tab, setTab] = useState<Tab>('overview');
  const { tablet } = useLayout();
  const header = <Header title="" />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const p = data.player;
  const age = p.bio?.birth ? Math.floor((TODAY - new Date(p.bio.birth).getTime()) / 3.15576e10) : null;
  const log = (p.log || []).slice().reverse();

  return (
    <Screen header={header}>
      {/* hero */}
      <View style={{ borderRadius: R.xl, overflow: 'hidden', backgroundColor: C.card, borderWidth: 1, borderColor: C.line }}>
        <LinearGradient colors={['#2A1F5A', '#151D35']} style={{ height: tablet ? 300 : 250 }}>
          <Txt style={{ position: 'absolute', right: 12, top: -10, fontFamily: F.display, fontSize: 160, color: 'rgba(255,255,255,0.05)' }}>{p.number}</Txt>
          {p.photo ? <Image source={asset(p.photo)} style={{ position: 'absolute', right: 0, bottom: 0, width: tablet ? 300 : 210, height: tablet ? 300 : 250 }} contentFit="cover" contentPosition="top" /> : null}
          <LinearGradient colors={['transparent', 'rgba(21,29,53,0.95)']} style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 120 }} />
          <View style={{ position: 'absolute', left: 18, bottom: 18, right: 120 }}>
            <Row style={{ gap: 8, marginBottom: 6 }}><TeamLogo code={p.team} size={26} /><Txt v="label" c={C.sub}>{p.team} · #{p.number}</Txt></Row>
            <Txt style={{ fontFamily: F.display, fontSize: tablet ? 46 : 38, lineHeight: tablet ? 46 : 38, color: C.txt, textShadowColor: 'rgba(0,0,0,0.75)', textShadowRadius: 12, textShadowOffset: { width: 0, height: 2 } }}>{titleCase(p.name).toUpperCase()}</Txt>
            <Row style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
              {p.pos ? <Pill label={lang === 'fr' ? POS[p.pos] || p.pos : p.pos} /> : null}
              {age ? <Pill label={`${age} ${lang === 'fr' ? 'ans' : 'y'}`} /> : null}
              {p.bio?.height ? <Pill label={`${p.bio.height} cm`} /> : null}
            </Row>
          </View>
        </LinearGradient>
      </View>

      <Row style={{ gap: 10, marginTop: 14 }}>
        <StatTile value={one(p.pts)} label={t('pts')} accent />
        <StatTile value={one(p.reb)} label={t('reb')} />
        <StatTile value={one(p.ast)} label={t('ast')} />
        <StatTile value={one(p.pir)} label={t('pir')} />
      </Row>

      <View style={{ marginTop: 16 }}>
        <Segmented<Tab> value={tab} onChange={setTab} items={[{ key: 'overview', label: t('seasonStats') }, { key: 'log', label: t('gameLog') }]} />
      </View>

      {tab === 'overview' ? (
        <View style={{ gap: 12, marginTop: 14 }}>
          <Card>
            <Row style={{ flexWrap: 'wrap', rowGap: 16 }}>
              {([['gp', p.gp], ['min', one(p.min)], ['stl', one(p.stl)], ['blk', one(p.blk)], ['tov', one(p.tov)], ['W', p.wins ?? '–']] as const).map(([k, v]) => (
                <View key={k} style={{ width: '33%', alignItems: 'center' }}><Txt v="num">{v}</Txt><Txt v="label">{k === 'W' ? t('won') : t(k)}</Txt></View>
              ))}
            </Row>
          </Card>
          <Card>
            <Txt v="label" style={{ marginBottom: 10 }}>{t('fg')} · {t('threes')} · {t('ft')}</Txt>
            {([[t('fg'), p.fg_pct, `${one(p.fgm)}/${one(p.fga)}`], [t('threes'), p.p3_pct, `${one(p.p3m)}/${one(p.p3a)}`], [t('ft'), p.ft_pct, `${one(p.ftm)}/${one(p.fta)}`]] as const).map(([l, v, sub]) => (
              <View key={l} style={{ marginVertical: 6 }}>
                <Row style={{ justifyContent: 'space-between', marginBottom: 5 }}><Txt v="sub">{l} <Txt v="small">{sub} {t('perGame')}</Txt></Txt><Txt v="h3">{pct(v)}</Txt></Row>
                <View style={{ height: 6, backgroundColor: C.glass, borderRadius: 3 }}><View style={{ width: `${Math.min(100, v || 0)}%`, height: 6, backgroundColor: C.orange, borderRadius: 3 }} /></View>
              </View>
            ))}
          </Card>
          {data.rank ? <Card><Txt v="sub">{lang === 'fr' ? 'Classement de l’évaluation' : 'Efficiency rank'} : <Txt v="h3" c={C.orange}>{data.rank}</Txt> / {data.of}</Txt></Card> : null}
        </View>
      ) : (
        <Card padded={false} style={{ marginTop: 14 }}>
          {log.map((r, i) => (
            <Pressable key={r.game_id} onPress={() => router.push(`/game/${r.game_id}`)}>
              <Row style={{ paddingHorizontal: 14, paddingVertical: 11, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                <View style={{ width: 54 }}><Txt v="small">{r.matchday || ''}</Txt><Txt v="small" c={C.sub}>{dayLabel(r.date, lang, { day: 'numeric', month: 'short' })}</Txt></View>
                <TeamLogo code={r.opp} size={28} />
                <View style={{ flex: 1 }}>
                  <Txt v="sub" c={C.txt}>{r.home === false ? '@ ' : ''}{r.opp}</Txt>
                  <Txt v="small" c={r.won ? C.good : C.bad} style={{ fontWeight: '700' }}>{r.won ? 'V' : 'D'} {r.score}</Txt>
                </View>
                <Txt v="num" c={C.orange} style={{ width: 34, textAlign: 'right', fontSize: 20 }}>{r.pts}</Txt>
                <Txt v="sub" style={{ width: 30, textAlign: 'right' }}>{r.reb}</Txt>
                <Txt v="sub" style={{ width: 30, textAlign: 'right' }}>{r.ast}</Txt>
              </Row>
            </Pressable>
          ))}
          <Row style={{ paddingHorizontal: 14, paddingVertical: 8, justifyContent: 'flex-end', gap: 0 }}>
            <Txt v="label" style={{ width: 34, textAlign: 'right' }}>{t('pts')}</Txt><Txt v="label" style={{ width: 30, textAlign: 'right' }}>{t('reb')}</Txt><Txt v="label" style={{ width: 30, textAlign: 'right' }}>{t('ast')}</Txt>
          </Row>
        </Card>
      )}
    </Screen>
  );
}
