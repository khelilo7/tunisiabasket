import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { Card, ErrorView, Loading, Row, Screen, Section, Segmented, TeamLogo, Txt } from '@/components/ui';
import { GameRow, N1 } from '@/components/nat1';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { Standing } from '@/lib/types';
import { C } from '@/theme';

type League = 'proa' | 'nat1';
type Nat1Row = { code: string; name: string; rank: number; w: number; l: number; pts: number; diff: number; final?: boolean };

export default function Standings() {
  const { t, fav, lang } = useApp();
  const [lg, setLg] = useState<League>('proa');
  const ov = useApi<{ season: string; standings: (Standing & { box?: number })[] }>('/api/overview');
  const n1 = useApi<N1 & { standings: Nat1Row[]; format?: { playoff: number } }>(lg === 'nat1' ? '/api/nat1' : null);
  const last = lg === 'nat1' ? (n1.data?.matchdays || []).filter(m => m.games.some(g => g.home_score != null)).slice(-1)[0] : undefined;
  const rows: (Standing | Nat1Row)[] = (lg === 'proa' ? ov.data?.standings : n1.data?.standings) || [];
  const cut = lg === 'proa' ? 6 : n1.data?.format?.playoff ?? 8;
  const src = lg === 'proa' ? ov : n1;

  return (
    <Screen onRefresh={src.refresh} refreshing={src.refreshing}>
      <Txt v="h1">{t('standings')}</Txt>
      <View style={{ marginTop: 12, marginBottom: 16 }}>
        <Segmented<League> value={lg} onChange={setLg} items={[{ key: 'proa', label: 'Pro A' }, { key: 'nat1', label: t('nat1') }]} />
      </View>
      {src.error && !src.data ? <ErrorView onRetry={src.refresh} /> : null}
      {!rows.length && !src.error ? <Loading /> : null}
      {rows.length ? (
        <Card padded={false}>
          <Row style={{ paddingHorizontal: 14, paddingVertical: 10 }}>
            <Txt v="label" style={{ width: 28 }}>#</Txt>
            <Txt v="label" style={{ flex: 1 }}>{t('team')}</Txt>
            <Txt v="label" style={{ width: 34, textAlign: 'center' }}>{t('w')}</Txt>
            <Txt v="label" style={{ width: 34, textAlign: 'center' }}>{t('l')}</Txt>
            <Txt v="label" style={{ width: 50, textAlign: 'center' }}>+/-</Txt>
            <Txt v="label" style={{ width: 38, textAlign: 'right' }}>PTS</Txt>
          </Row>
          {rows.map((r, i) => {
            const zone = r.rank <= cut ? C.orange : C.blue;
            return (
              <Pressable key={r.code} onPress={() => router.push(lg === 'proa' ? `/team/${r.code}` : `/nat1/${r.code}`)}>
                <Row style={{ paddingHorizontal: 14, paddingVertical: 12, borderTopWidth: 1, borderColor: i === cut ? 'rgba(255,138,31,0.5)' : C.line, backgroundColor: r.code === fav ? 'rgba(255,138,31,0.08)' : undefined }}>
                  <View style={{ position: 'absolute', left: 0, top: 10, bottom: 10, width: 3, borderRadius: 2, backgroundColor: zone }} />
                  <Txt v="num" c={r.rank <= 4 ? C.orange : C.sub} style={{ width: 28, fontSize: 18 }}>{r.rank}</Txt>
                  <Row style={{ flex: 1, gap: 10 }}>
                    <TeamLogo code={r.code} size={30} />
                    <Txt v="h3" style={{ flex: 1, fontWeight: '600' }} numberOfLines={1}>{r.name}</Txt>
                  </Row>
                  <Txt v="sub" style={{ width: 34, textAlign: 'center' }}>{r.w}</Txt>
                  <Txt v="sub" style={{ width: 34, textAlign: 'center' }}>{r.l}</Txt>
                  <Txt v="sub" c={r.diff > 0 ? C.good : r.diff < 0 ? C.bad : C.sub} style={{ width: 50, textAlign: 'center' }}>{r.diff > 0 ? '+' : ''}{r.diff}</Txt>
                  <Txt v="num" style={{ width: 38, textAlign: 'right', fontSize: 19 }}>{r.pts}</Txt>
                </Row>
              </Pressable>
            );
          })}
        </Card>
      ) : null}
      {rows.length ? (
        <Row style={{ gap: 16, marginTop: 12 }}>
          <Row style={{ gap: 6 }}><View style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: C.orange }} /><Txt v="small">{lg === 'proa' ? `${t('playoff')} · ${t('topSix')}` : t('playoff')}</Txt></Row>
          <Row style={{ gap: 6 }}><View style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: C.blue }} /><Txt v="small">{lg === 'proa' ? `${t('playout')} · ${t('others')}` : ''}</Txt></Row>
        </Row>
      ) : null}
      <Txt v="small" style={{ marginTop: 10 }}>{t('w')} 2 pts · {t('l')} 1 pt · FTBB art. 182–184{rows.some((r) => r.final === false) ? ` · ${t('rankProvisional')}` : ''}</Txt>
      {last ? (
        <Section title={`${t('matchday')} ${last.matchday}`}>
          <Card padded={false}>{last.games.map((g, i) => <GameRow key={g.home + g.away} g={g} md={last.matchday} first={!i} />)}</Card>
          <Txt v="small" style={{ marginTop: 8 }}>{t('nat1')} · {lang === 'fr' ? 'touche un club pour tous ses matchs' : 'tap a club for all its games'}</Txt>
        </Section>
      ) : null}
    </Screen>
  );
}
