import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { C, R } from '@/theme';
import { Section, tap, Txt, useLayout } from './ui';

// The fans' corner of the home screen: predictions, the player-of-the-round / MVP vote, the play of the week. A red dot marks what is open now.
type Predict = { round: null | { matchday: number; open: boolean; picked: number; of: number } };
type Round = { round: number | null; open?: boolean; my_vote?: string | null; history: { round: number; winner: { name: string } }[] };
type Plays = { week: null | { title: string; open: boolean; my_vote: string | null; clips: { thumb: string | null }[]; winner: { thumb: string | null } | null } };

export function FanZone() {
  const { vid, lang } = useApp();
  const fr = lang === 'fr';
  const { tablet } = useLayout();
  const p = useApi<Predict>(vid ? `/api/predict?vid=${vid}` : null).data?.round;
  const r = useApi<Round>(vid ? `/api/round?vid=${vid}` : null).data;
  const w = useApi<Plays>(vid ? `/api/plays?vid=${vid}` : null).data?.week;
  const thumb = w?.winner?.thumb || w?.clips.find(c => c.thumb)?.thumb;
  const tiles = [
    { k: 'predict', icon: 'analytics' as const, color: C.blue, title: fr ? 'Pronostics' : 'Predictions',
      sub: p ? (p.open ? `J${p.matchday} · ${p.picked}/${p.of}` : `J${p.matchday} · ${fr ? 'fermés' : 'closed'}`) : (fr ? 'Bientôt' : 'Soon'),
      live: !!p?.open && p.picked < p.of, go: () => router.push('/votes?tab=predict') },
    { k: 'round', icon: 'star' as const, color: C.amber, title: fr ? 'Joueur de la sem.' : 'Player of the week',
      sub: r?.round ? (r.open ? (r.my_vote ? (fr ? 'A voté ✓' : 'Voted ✓') : (fr ? `J${r.round} · vote ouvert` : `R${r.round} · voting open`)) : `J${r.round}`)
        : r?.history[0] ? `J${r.history[0].round} · ${r.history[0].winner.name}` : (fr ? 'Bientôt' : 'Soon'),
      live: !!r?.open && !r.my_vote, go: () => router.push('/votes?tab=round') },
    { k: 'plays', icon: 'play-circle' as const, color: C.red, title: fr ? 'Action de la sem.' : 'Play of the week', thumb,
      sub: w ? (w.open ? (w.my_vote ? (fr ? 'A voté ✓' : 'Voted ✓') : (fr ? 'Vote ouvert' : 'Voting open')) : w.title) : (fr ? 'Bientôt' : 'Soon'),
      live: !!w?.open && !w.my_vote, go: () => router.push('/plays') },
  ];
  return (
    <Section title={fr ? 'Espace fans' : 'Fan zone'}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
        {tiles.map(x => (
          <Pressable key={x.k} onPress={() => { tap(); x.go(); }} style={({ pressed }) => [s.tile, { width: tablet ? 220 : 150 }, pressed && { opacity: 0.8 }]}>
            {x.thumb ? <><Image source={{ uri: x.thumb }} style={StyleSheet.absoluteFill} contentFit="cover" /><View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(11,16,32,0.62)' }]} /></> : null}
            <View style={[s.icon, { backgroundColor: x.color + '26' }]}><Ionicons name={x.icon} size={20} color={x.color} /></View>
            <Txt v="h3" numberOfLines={1} style={{ marginTop: 12 }}>{x.title}</Txt>
            <Txt v="small" c={x.live ? C.txt : C.sub} numberOfLines={1}>{x.sub}</Txt>
            {x.live ? <View style={s.dot} /> : null}
          </Pressable>
        ))}
      </ScrollView>
    </Section>
  );
}

// The club's pages (set in the website's admin): round brand icons, shown only when the address exists.
const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = { facebook: 'logo-facebook', youtube: 'logo-youtube', instagram: 'logo-instagram', x: 'logo-x', tiktok: 'logo-tiktok' };
const BRAND: Record<string, string> = { facebook: '#1877F2', youtube: '#FF0033', instagram: '#E1306C', x: '#FFFFFF', tiktok: '#FFFFFF' };

export function SocialLinks({ big }: { big?: boolean }) {
  const { lang } = useApp();
  const links = (useApi<{ links: { key: string; name: string; url: string }[] }>('/api/social').data?.links || []).filter(l => ICONS[l.key] && l.url);
  if (!links.length) return null;
  return (
    <View style={{ alignItems: 'center', marginTop: big ? 0 : 28, gap: 10 }}>
      <Txt v="label">{lang === 'fr' ? 'Suis-nous' : 'Follow us'}</Txt>
      <View style={{ flexDirection: 'row', gap: 14 }}>
        {links.map(l => (
          <Pressable key={l.key} onPress={() => { tap(); Linking.openURL(l.url); }} accessibilityRole="link" accessibilityLabel={l.name} hitSlop={6}
            style={({ pressed }) => [s.social, big && { width: 52, height: 52, borderRadius: 26 }, pressed && { opacity: 0.7 }]}>
            <Ionicons name={ICONS[l.key]} size={big ? 24 : 20} color={BRAND[l.key]} />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  tile: { height: 128, borderRadius: R.lg, padding: 14, backgroundColor: C.card, borderWidth: 1, borderColor: C.line, overflow: 'hidden' },
  icon: { width: 38, height: 38, borderRadius: R.sm, alignItems: 'center', justifyContent: 'center' },
  dot: { position: 'absolute', top: 12, right: 12, width: 9, height: 9, borderRadius: 5, backgroundColor: C.bad },
  social: { width: 44, height: 44, borderRadius: 22, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center' },
});
