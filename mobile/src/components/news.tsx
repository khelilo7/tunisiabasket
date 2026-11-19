import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { View } from 'react-native';

import { useApp } from '@/lib/app-state';
import { dayLabel } from '@/lib/format';
import { C } from '@/theme';
import { Avatar, Card, Row, tap, TeamLogo, Txt } from './ui';

export type News = { id: string; label: string; title: string; title_en?: string; body?: string; body_en?: string; date: string; pinned?: boolean; team?: string; player?: string; player_name?: string; photo?: string | null;
  match?: { home: string; away: string; home_name: string; away_name: string; home_score: number; away_score: number; md?: number | null } | null };

export const NEWS_LABEL: Record<string, { fr: string; en: string; color: string; icon: keyof typeof Ionicons.glyphMap }> = {
  official: { fr: 'Officiel', en: 'Official', color: '#5B8CFF', icon: 'megaphone' },
  injury: { fr: 'Blessure', en: 'Injury', color: '#FF5D6C', icon: 'medkit' },
  transfer: { fr: 'Transfert', en: 'Transfer', color: '#7C5CFF', icon: 'swap-horizontal' },
  result: { fr: 'Résultat', en: 'Result', color: '#3ECF8E', icon: 'basketball' },
  interview: { fr: 'Interview', en: 'Interview', color: '#FFB547', icon: 'mic' },
  info: { fr: 'Info', en: 'Info', color: '#8790AD', icon: 'information-circle' },
};

// One news item: a coloured label, the date, the title; the game's score with both clubs when it announces one; the player's photo or the club's logo; the text opens on a tap.
export function NewsCard({ n }: { n: News }) {
  const { lang } = useApp();
  const [open, setOpen] = useState(false);
  const L = NEWS_LABEL[n.label] || NEWS_LABEL.info;
  const title = (lang === 'en' && n.title_en) || n.title;
  const body = (lang === 'en' && n.body_en) || n.body || '';
  const long = body.length > 120;
  return (
    <Card onPress={long ? () => { tap(); setOpen(!open); } : undefined}>
      <Row style={{ gap: 12, alignItems: 'flex-start' }}>
        {n.player ? <Avatar photo={n.photo} name={n.player_name || n.title} size={48} team={n.team} /> : n.team ? <TeamLogo code={n.team} size={48} /> : (
          <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: L.color + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={L.icon} size={22} color={L.color} /></View>
        )}
        <View style={{ flex: 1 }}>
          <Row style={{ gap: 8, marginBottom: 4 }}>
            <View style={{ backgroundColor: L.color + '26', borderRadius: 99, paddingHorizontal: 8, paddingVertical: 2 }}><Txt v="small" c={L.color} style={{ fontWeight: '800', fontSize: 11 }}>{L[lang].toUpperCase()}</Txt></View>
            <Txt v="small">{dayLabel(n.date, lang, { day: 'numeric', month: 'short' })}</Txt>
            {n.pinned ? <Ionicons name="pin" size={12} color={C.amber} /> : null}
          </Row>
          <Txt v="h3" style={{ lineHeight: 21 }}>{title}</Txt>
          {n.match ? (
            <Row style={{ gap: 8, marginTop: 8, backgroundColor: C.card2, borderRadius: 12, padding: 8, alignSelf: 'flex-start' }}>
              <TeamLogo code={n.match.home} size={24} /><Txt v="sub" c={C.txt}>{n.match.home}</Txt>
              <Txt v="num" style={{ fontSize: 18 }}>{n.match.home_score}–{n.match.away_score}</Txt>
              <Txt v="sub" c={C.txt}>{n.match.away}</Txt><TeamLogo code={n.match.away} size={24} />
            </Row>
          ) : null}
          {body ? <Txt v="sub" numberOfLines={open ? undefined : 2} style={{ marginTop: 6 }}>{body}</Txt> : null}
          {long ? <Txt v="small" c={C.orange} style={{ marginTop: 4, fontWeight: '700' }}>{open ? (lang === 'fr' ? 'Réduire' : 'Show less') : (lang === 'fr' ? 'Lire la suite' : 'Read more')}</Txt> : null}
        </View>
      </Row>
    </Card>
  );
}
