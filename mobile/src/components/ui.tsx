import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { ReactNode, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, RefreshControl, ScrollView, StyleProp, StyleSheet, Text, TextProps, TextStyle, useWindowDimensions, View, ViewStyle } from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '@/lib/app-state';
import { asset, teamLogo } from '@/lib/api';
import { C, F, GRAD, MAX_W, R, S, TABLET } from '@/theme';

// Back: to the previous screen, or home when the page was opened directly (a link, a notification, the web address bar).
export const goBack = () => (router.canGoBack() ? router.back() : router.replace('/'));

export const tap = () => { if (Platform.OS !== 'web') Haptics.selectionAsync().catch(() => {}); };

export function useLayout() {
  const { width } = useWindowDimensions();
  const tablet = width >= TABLET;
  return { width, tablet, cols: width >= 1100 ? 3 : tablet ? 2 : 1, pad: tablet ? 28 : 16 };
}

// ---------------------------------------------------------------- text
type TxtProps = TextProps & { v?: 'h1' | 'h2' | 'h3' | 'body' | 'sub' | 'small' | 'label' | 'num' | 'numXL' | 'numL'; c?: string; style?: StyleProp<TextStyle> };
export function Txt({ v = 'body', c, style, ...p }: TxtProps) {
  return <Text {...p} style={[T[v], c ? { color: c } : null, style]} />;
}
const T = StyleSheet.create({
  h1: { color: C.txt, fontFamily: F.display, fontSize: 34, letterSpacing: 0.3, textTransform: 'uppercase' },
  h2: { color: C.txt, fontFamily: F.display, fontSize: 24, letterSpacing: 0.3, textTransform: 'uppercase' },
  h3: { color: C.txt, fontSize: 16, fontWeight: '700' },
  body: { color: C.txt, fontSize: 15 },
  sub: { color: C.sub, fontSize: 14 },
  small: { color: C.mut, fontSize: 12 },
  label: { color: C.mut, fontSize: 11, fontWeight: '700', letterSpacing: 1.2, textTransform: 'uppercase' },
  num: { color: C.txt, fontFamily: F.display, fontSize: 22 },
  numL: { color: C.txt, fontFamily: F.display, fontSize: 32 },
  numXL: { color: C.txt, fontFamily: F.display, fontSize: 48, lineHeight: 52 },
});

// ---------------------------------------------------------------- page
export function Screen({ children, onRefresh, refreshing, scroll = true, header, padBottom = true }: { children: ReactNode; onRefresh?: () => void; refreshing?: boolean; scroll?: boolean; header?: ReactNode; padBottom?: boolean }) {
  const ins = useSafeAreaInsets();
  const { pad } = useLayout();
  const body = <View style={{ width: '100%', maxWidth: MAX_W, alignSelf: 'center', paddingHorizontal: pad }}>{children}</View>;
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <LinearGradient colors={['#1A2350', '#0E1430', C.bg]} locations={[0, 0.35, 0.8]} style={StyleSheet.absoluteFill} />
      <View style={st.glowRed} pointerEvents="none" />
      {header}
      {scroll ? (
        <ScrollView contentContainerStyle={{ paddingTop: header ? 8 : ins.top + 12, paddingBottom: padBottom ? ins.bottom + (header ? 32 : 100) : 24 }}
          refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={C.orange} colors={[C.orange]} /> : undefined}
          showsVerticalScrollIndicator={false}>
          {body}
        </ScrollView>
      ) : body}
    </View>
  );
}

export function Header({ title, onBack, right }: { title?: string; onBack?: () => void; right?: ReactNode }) {
  const ins = useSafeAreaInsets();
  const { pad } = useLayout();
  return (
    <View style={{ paddingTop: ins.top + 6, paddingHorizontal: pad, paddingBottom: 6, flexDirection: 'row', alignItems: 'center', gap: 12, maxWidth: MAX_W, width: '100%', alignSelf: 'center' }}>
      <IconBtn name="chevron-back" onPress={onBack || goBack} />
      <Txt v="h3" style={{ flex: 1, fontSize: 18 }} numberOfLines={1}>{title}</Txt>
      {right}
    </View>
  );
}

export function IconBtn({ name, onPress, active }: { name: keyof typeof Ionicons.glyphMap; onPress?: () => void; active?: boolean }) {
  return (
    <Pressable onPress={() => { tap(); onPress?.(); }} style={({ pressed }) => [st.iconBtn, active && { backgroundColor: C.orange }, pressed && { opacity: 0.7 }]} hitSlop={8}>
      <Ionicons name={name} size={20} color={active ? '#1A1205' : C.txt} />
    </Pressable>
  );
}

// ---------------------------------------------------------------- surfaces
export function Card({ children, style, onPress, padded = true, glow }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; padded?: boolean; glow?: string }) {
  const inner = (
    <View style={[st.card, padded && { padding: S.lg }, glow ? { borderColor: glow } : null, style]}>
      <LinearGradient colors={GRAD.card} style={[StyleSheet.absoluteFill, { borderRadius: R.lg }]} pointerEvents="none" />
      {children}
    </View>
  );
  if (!onPress) return inner;
  return <Pressable onPress={() => { tap(); onPress(); }} style={({ pressed }) => [{ transform: [{ scale: pressed ? 0.985 : 1 }] }]}>{inner}</Pressable>;
}

export function HeroCard({ children, colors = GRAD.hero, style, onPress }: { children: ReactNode; colors?: readonly [string, string, ...string[]]; style?: StyleProp<ViewStyle>; onPress?: () => void }) {
  return (
    <Pressable disabled={!onPress} onPress={() => { tap(); onPress?.(); }} style={({ pressed }) => [{ transform: [{ scale: pressed ? 0.985 : 1 }] }]}>
      <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[{ borderRadius: R.xl, padding: S.xl, overflow: 'hidden' }, style]}>
        <View style={st.heroShine} pointerEvents="none" />
        {children}
      </LinearGradient>
    </Pressable>
  );
}

export function Section({ title, action, onAction, children, style }: { title: string; action?: string; onAction?: () => void; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[{ marginTop: S.xxl }, style]}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: S.md }}>
        <Txt v="h2">{title}</Txt>
        {action ? <Pressable onPress={() => { tap(); onAction?.(); }} hitSlop={10}><Txt v="sub" c={C.orange} style={{ fontWeight: '700' }}>{action} ›</Txt></Pressable> : null}
      </View>
      {children}
    </View>
  );
}

export function Grid({ children, min = 1, gap = S.md }: { children: ReactNode[]; min?: number; gap?: number }) {
  const { cols } = useLayout();
  const n = Math.max(min, cols);
  if (n === 1) return <View style={{ gap }}>{children}</View>;
  const rows: ReactNode[][] = [];
  children.forEach((c, i) => { if (i % n === 0) rows.push([]); rows[rows.length - 1].push(c); });
  return (
    <View style={{ gap }}>
      {rows.map((r, i) => (
        <View key={i} style={{ flexDirection: 'row', gap }}>
          {r.map((c, j) => <View key={j} style={{ flex: 1 }}>{c}</View>)}
          {Array.from({ length: n - r.length }).map((_, j) => <View key={'e' + j} style={{ flex: 1 }} />)}
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------- controls
export function Chips<K extends string>({ items, value, onChange, scroll = true }: { items: { key: K; label: string }[]; value: K; onChange: (k: K) => void; scroll?: boolean }) {
  const row = items.map(it => {
    const on = it.key === value;
    return (
      <Pressable key={it.key} onPress={() => { tap(); onChange(it.key); }} style={[st.chip, on && st.chipOn]}>
        <Txt v="sub" c={on ? '#1A1205' : C.sub} style={{ fontWeight: '700' }}>{it.label}</Txt>
      </Pressable>
    );
  });
  return scroll ? <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 2 }}>{row}</ScrollView> : <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{row}</View>;
}

export function Segmented<K extends string>({ items, value, onChange }: { items: { key: K; label: string }[]; value: K; onChange: (k: K) => void }) {
  return (
    <View style={st.seg}>
      {items.map(it => {
        const on = it.key === value;
        return (
          <Pressable key={it.key} onPress={() => { tap(); onChange(it.key); }} style={[st.segItem, on && st.segOn]}>
            <Txt v="sub" c={on ? C.txt : C.mut} style={{ fontWeight: '700' }}>{it.label}</Txt>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Pill({ label, color = C.glassStrong, text = C.txt, icon }: { label: string; color?: string; text?: string; icon?: keyof typeof Ionicons.glyphMap }) {
  return (
    <View style={[st.pill, { backgroundColor: color }]}>
      {icon ? <Ionicons name={icon} size={12} color={text} /> : null}
      <Txt v="small" c={text} style={{ fontWeight: '800', letterSpacing: 0.4 }}>{label}</Txt>
    </View>
  );
}

// ---------------------------------------------------------------- media
export function TeamLogo({ code, size = 40, ring = true }: { code?: string | null; size?: number; ring?: boolean }) {
  const [bad, setBad] = useState(false);
  const inner = size * 0.78;
  return (
    <View style={[{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center' }, ring && { backgroundColor: '#F4F6FB' }]}>
      {code && !bad ? <Image source={teamLogo(code)} style={{ width: inner, height: inner }} contentFit="contain" onError={() => setBad(true)} transition={150} />
        : <Txt v="label" c={ring ? '#1A2140' : C.sub} style={{ fontSize: size * 0.26 }}>{(code || '?').slice(0, 3)}</Txt>}
    </View>
  );
}

export function Avatar({ photo, name, size = 48, team }: { photo?: string | null; name?: string; size?: number; team?: string }) {
  const [bad, setBad] = useState(false);
  const initials = (name || '?').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase();
  return (
    <View style={{ width: size, height: size }}>
      <View style={{ width: size, height: size, borderRadius: size / 2, overflow: 'hidden', backgroundColor: C.card2, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: C.lineStrong }}>
        {photo && !bad ? <Image source={asset(photo)} style={{ width: size, height: size }} contentFit="cover" contentPosition="top" onError={() => setBad(true)} transition={150} />
          : <Txt v="num" c={C.sub} style={{ fontSize: size * 0.36 }}>{initials}</Txt>}
      </View>
      {team ? <View style={{ position: 'absolute', right: -2, bottom: -2 }}><TeamLogo code={team} size={size * 0.42} /></View> : null}
    </View>
  );
}

// ---------------------------------------------------------------- small pieces
export function StatTile({ value, label, accent, style }: { value: string | number; label: string; accent?: boolean; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[st.tile, accent && { borderColor: C.orange }, style]}>
      <Txt v="numL" c={accent ? C.orange : C.txt}>{value}</Txt>
      <Txt v="label">{label}</Txt>
    </View>
  );
}

export function CompareBar({ label, a, b, fmt = (x: number) => String(x) }: { label: string; a: number; b: number; fmt?: (x: number) => string }) {
  const tot = a + b || 1;
  return (
    <View style={{ marginVertical: 7 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 5 }}>
        <Txt v="h3" c={a >= b ? C.txt : C.mut}>{fmt(a)}</Txt>
        <Txt v="small">{label}</Txt>
        <Txt v="h3" c={b >= a ? C.txt : C.mut}>{fmt(b)}</Txt>
      </View>
      <View style={{ flexDirection: 'row', gap: 4, height: 6 }}>
        <View style={{ flex: a / tot, backgroundColor: a >= b ? C.orange : C.glassStrong, borderRadius: 3 }} />
        <View style={{ flex: b / tot, backgroundColor: b > a ? C.blue : C.glassStrong, borderRadius: 3 }} />
      </View>
    </View>
  );
}

export function Loading() {
  return <View style={{ paddingVertical: 60, alignItems: 'center' }}><ActivityIndicator color={C.orange} /></View>;
}

export function ErrorView({ onRetry }: { onRetry?: () => void }) {
  const { t } = useApp();
  return (
    <Card style={{ alignItems: 'center', gap: 10, marginTop: 20 }}>
      <Ionicons name="cloud-offline-outline" size={30} color={C.mut} />
      <Txt v="sub">{t('offline')}</Txt>
      {onRetry ? <Pressable onPress={onRetry} style={[st.chip, st.chipOn]}><Txt v="sub" c="#1A1205" style={{ fontWeight: '700' }}>{t('retry')}</Txt></Pressable> : null}
    </Card>
  );
}

export function Empty({ text }: { text: string }) {
  return <Card style={{ alignItems: 'center', paddingVertical: 28 }}><Txt v="sub">{text}</Txt></Card>;
}

export const Row = ({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) => <View style={[{ flexDirection: 'row', alignItems: 'center' }, style]}>{children}</View>;

export const st = StyleSheet.create({
  card: { backgroundColor: C.card, borderRadius: R.lg, borderWidth: 1, borderColor: C.line, overflow: 'hidden' },
  glowRed: { position: 'absolute', top: -140, right: -120, width: 320, height: 320, borderRadius: 160, backgroundColor: 'rgba(238,75,82,0.18)' },
  heroShine: { position: 'absolute', top: -60, right: -40, width: 200, height: 200, borderRadius: 100, backgroundColor: 'rgba(255,255,255,0.12)' },
  iconBtn: { width: 42, height: 42, borderRadius: 14, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center' },
  chip: { paddingHorizontal: 16, paddingVertical: 9, borderRadius: R.pill, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  chipOn: { backgroundColor: C.orange, borderColor: C.orange },
  seg: { flexDirection: 'row', backgroundColor: C.glass, borderRadius: R.pill, padding: 4, borderWidth: 1, borderColor: C.line },
  segItem: { flex: 1, paddingVertical: 9, borderRadius: R.pill, alignItems: 'center' },
  segOn: { backgroundColor: C.card2, borderWidth: 1, borderColor: C.lineStrong },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 4, borderRadius: R.pill, alignSelf: 'flex-start' },
  tile: { flex: 1, backgroundColor: C.card2, borderRadius: R.md, paddingVertical: 12, alignItems: 'center', borderWidth: 1, borderColor: C.line },
});
