import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, TextInput, View } from 'react-native';

import { Avatar, Card, Chips, ErrorView, Grid, HeroCard, Loading, Row, Screen, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { one, titleCase } from '@/lib/format';
import { Player } from '@/lib/types';
import { C, F, GRAD, R } from '@/theme';

type K = 'pts' | 'reb' | 'ast' | 'stl' | 'blk' | 'pir';

export default function Players() {
  const { t } = useApp();
  const { data, error, refresh, refreshing } = useApi<{ players: (Player & { qualified?: boolean })[] }>('/api/players');
  const [k, setK] = useState<K>('pts');
  const [q, setQ] = useState('');
  const list = useMemo(() => {
    const all = data?.players || [];
    if (q.trim()) {
      const n = q.trim().toLowerCase();
      return all.filter(p => p.name.toLowerCase().includes(n) || p.team.toLowerCase() === n);
    }
    return all.filter(p => p.qualified !== false && p.gp > 0).sort((a, b) => b[k] - a[k]).slice(0, 30);
  }, [data, k, q]);
  const lead = !q && list[0];
  const label: Record<K, string> = { pts: t('points'), reb: t('rebounds'), ast: t('assists'), stl: t('steals'), blk: t('blocks'), pir: t('efficiency') };

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Txt v="h1">{t('players')}</Txt>
      <Row style={{ marginTop: 12, backgroundColor: C.glass, borderRadius: R.pill, borderWidth: 1, borderColor: C.line, paddingHorizontal: 14, gap: 8 }}>
        <Ionicons name="search" size={18} color={C.mut} />
        <TextInput value={q} onChangeText={setQ} placeholder={t('search')} placeholderTextColor={C.mut} style={{ flex: 1, color: C.txt, paddingVertical: 11, fontSize: 15 }} autoCorrect={false} />
        {q ? <Pressable onPress={() => setQ('')}><Ionicons name="close-circle" size={18} color={C.mut} /></Pressable> : null}
      </Row>
      {!q ? <View style={{ marginTop: 12 }}><Chips<K> value={k} onChange={setK} items={(Object.keys(label) as K[]).map(x => ({ key: x, label: label[x] }))} /></View> : null}
      {error && !data ? <ErrorView onRetry={refresh} /> : null}
      {!data && !error ? <Loading /> : null}

      {lead ? (
        <View style={{ marginTop: 16 }}>
          <HeroCard colors={GRAD.violet} onPress={() => router.push(`/player/${lead.id}`)}>
            <Row style={{ gap: 14 }}>
              <View style={{ flex: 1 }}>
                <Txt v="label" c="rgba(255,255,255,0.8)">{label[k]} · {t('perGame')}</Txt>
                <Txt style={{ fontFamily: F.display, fontSize: 30, color: '#fff', marginTop: 4 }} numberOfLines={2}>{titleCase(lead.name).toUpperCase()}</Txt>
                <Txt v="sub" c="rgba(255,255,255,0.85)">{lead.team} · #{lead.number}</Txt>
                <Txt style={{ fontFamily: F.display, fontSize: 56, lineHeight: 60, color: '#fff' }}>{one(lead[k])}</Txt>
              </View>
              <Avatar photo={lead.photo} name={lead.name} size={110} team={lead.team} />
            </Row>
          </HeroCard>
        </View>
      ) : null}

      <View style={{ marginTop: 14 }}>
        <Grid>
          {list.slice(lead ? 1 : 0).map((p, i) => (
            <Card key={p.id} onPress={() => router.push(`/player/${p.id}`)} style={{ paddingVertical: 12 }}>
              <Row style={{ gap: 12 }}>
                {!q ? <Txt v="num" c={C.mut} style={{ width: 26, fontSize: 18 }}>{i + 2}</Txt> : null}
                <Avatar photo={p.photo} name={p.name} size={44} team={p.team} />
                <View style={{ flex: 1 }}>
                  <Txt v="h3" numberOfLines={1}>{titleCase(p.name)}</Txt>
                  <Txt v="small">{p.team} · {p.gp} {t('gp')} · {one(p.min)} min</Txt>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Txt v="num" c={C.orange}>{one(q ? p.pts : p[k])}</Txt>
                  <Txt v="label" style={{ fontSize: 9 }}>{q ? t('pts') : t(k)}</Txt>
                </View>
              </Row>
            </Card>
          ))}
        </Grid>
      </View>
    </Screen>
  );
}
