import { router } from 'expo-router';
import { View } from 'react-native';

import { useApp } from '@/lib/app-state';
import { dayLabel, titleCase } from '@/lib/format';
import { GameSummary, PlanGame } from '@/lib/types';
import { C } from '@/theme';
import { Card, Pill, Row, TeamLogo, Txt } from './ui';


// A played game: two clubs, the score in the middle, the winner bright and the loser dim (as the reference apps do).
export function GameCard({ g, compact }: { g: GameSummary; compact?: boolean }) {
  const { t, lang } = useApp();
  const [a, b] = g.teams;
  const won = (x: typeof a, y: typeof b) => x.won ?? x.points > y.points;
  return (
    <Card onPress={g.id ? () => router.push(`/game/${g.id}`) : undefined} style={{ paddingVertical: compact ? 14 : 18 }}>
      <Row style={{ justifyContent: 'space-between', marginBottom: compact ? 8 : 12 }}>
        <Txt v="label">{g.matchday ? `${t('matchday')} ${g.matchday.replace(/^J/, '')} · ` : ''}{dayLabel(g.date, lang)}</Txt>
        {g.id ? <Pill label={t('final').toUpperCase()} /> : <Pill label={t('noBox')} color="transparent" text={C.mut} />}
      </Row>
      <Row>
        <Side code={a.code} name={a.name} on={won(a, b)} />
        <Row style={{ gap: 10, paddingHorizontal: 6 }}>
          <Txt v={compact ? 'num' : 'numL'} c={won(a, b) ? C.txt : C.mut}>{a.points}</Txt>
          <Txt v="small">–</Txt>
          <Txt v={compact ? 'num' : 'numL'} c={won(b, a) ? C.txt : C.mut}>{b.points}</Txt>
        </Row>
        <Side code={b.code} name={b.name} on={won(b, a)} right />
      </Row>
      {!compact && g.mvp ? (
        <Row style={{ marginTop: 12, gap: 8 }}>
          <Pill label="MVP" color={C.orange} text="#1A1205" />
          <Txt v="small" numberOfLines={1} style={{ flex: 1 }}><Txt v="small" c={C.sub} style={{ fontWeight: '700' }}>{titleCase(g.mvp.name)}</Txt> · {g.mvp.pts} {t('pts')} · {g.mvp.reb} {t('reb')} · {g.mvp.ast} {t('ast')}</Txt>
        </Row>
      ) : null}
    </Card>
  );
}

function Side({ code, name, on, right }: { code: string; name: string; on: boolean; right?: boolean }) {
  return (
    <View style={{ flex: 1, alignItems: right ? 'flex-end' : 'flex-start', gap: 6 }}>
      <TeamLogo code={code} size={44} />
      <Txt v="sub" c={on ? C.txt : C.mut} numberOfLines={1} style={{ fontWeight: on ? '700' : '500', textAlign: right ? 'right' : 'left' }}>{name}</Txt>
    </View>
  );
}

// A game still to play: clubs, date and time.
export function FixtureCard({ g, date, names }: { g: PlanGame; date: string; names: Record<string, string> }) {
  const { t, lang } = useApp();
  return (
    <Card style={{ paddingVertical: 16 }}>
      <Row>
        <Side code={g.home} name={names[g.home] || g.home} on />
        <View style={{ alignItems: 'center', paddingHorizontal: 8, gap: 2 }}>
          <Txt v="num" c={C.txt}>{g.time || '––:––'}</Txt>
          <Txt v="small">{dayLabel(g.game_date || date, lang)}</Txt>
          {!g.time ? <Txt v="small" c={C.mut} style={{ fontSize: 10 }}>{t('tbd')}</Txt> : null}
        </View>
        <Side code={g.away} name={names[g.away] || g.away} on right />
      </Row>
    </Card>
  );
}
