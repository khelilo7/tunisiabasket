import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Avatar, Row, tap, TeamLogo, Txt, useLayout } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { dayLabel, titleCase } from '@/lib/format';
import { C, F, R } from '@/theme';
import { FPlayer } from './types';

type Part = { key: string; label: string; count: number; points: number };
type Game = { md: number; date: string; game_id: string; opp: string; home: boolean | null; score: string; won: boolean; played: boolean; fp: number | null; breakdown: Part[];
  line: { min: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number; pf: number; fgm: number; fga: number; ftm: number; fta: number; pm: number | null } };
type View_ = FPlayer & { games: Game[]; avg_breakdown: Part[]; best: number | null; worst: number | null; last: number | null; real: { pts: number; reb: number; ast: number; min: number } };

const FR: Record<string, string> = {
  Points: 'Points', Rebounds: 'Rebonds', Assists: 'Passes', Steals: 'Interceptions', Blocks: 'Contres', 'Three-pointers made': 'Paniers à 3 pts',
  'Missed shots': 'Tirs manqués', 'Missed free throws': 'Lancers manqués', Turnovers: 'Balles perdues', Fouls: 'Fautes', 'Plus-minus': '+/- sur le terrain',
  'Double-double': 'Double-double', 'Triple-double': 'Triple-double',
};

export const fpColor = (v?: number | null) => (v == null ? C.mut : v < 0 ? C.bad : v >= 25 ? C.good : C.txt);
export const fpText = (v?: number | null) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`);

// A player seen the fantasy way: what he costs, what he scores on average and game by game, and where each point comes from (or goes).
export function PlayerSheet({ id, onClose, action }: { id: string; onClose: () => void; action?: { label: string; danger?: boolean; disabled?: boolean; onPress: () => void } }) {
  const { lang, t } = useApp();
  const ins = useSafeAreaInsets();
  const { tablet } = useLayout();
  const { data: p } = useApi<View_>(`/api/fantasy/player/${id}`);
  const [open, setOpen] = useState<string | null>(null);
  const L = (s: string) => (lang === 'fr' ? FR[s] || s : s);
  return (
    <Modal transparent animationType="slide" visible onRequestClose={onClose} statusBarTranslucent>
      <Pressable style={s.backdrop} onPress={onClose} />
      <View style={[s.sheet, { paddingBottom: ins.bottom + 12 }, tablet && s.tablet]}>
        <View style={s.grip} />
        {!p ? <Txt v="sub" style={{ padding: 30, textAlign: 'center' }}>{t('loading')}</Txt> : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 10 }}>
            <Row style={{ gap: 14 }}>
              <Avatar photo={p.photo} name={p.name} size={68} team={p.team} />
              <View style={{ flex: 1 }}>
                <Txt style={{ fontFamily: F.display, fontSize: 26, color: C.txt }} numberOfLines={1}>{titleCase(p.name).toUpperCase()}</Txt>
                <Txt v="small">{p.pos} · {p.team} · #{p.number} · {p.gp} {lang === 'fr' ? 'matchs' : 'games'}</Txt>
              </View>
              <View style={s.price}><Txt v="label" style={{ fontSize: 8 }}>{lang === 'fr' ? 'PRIX' : 'PRICE'}</Txt><Txt v="num" c={C.amber} style={{ fontSize: 22 }}>{p.price.toFixed(1)}</Txt></View>
            </Row>

            {/* fantasy numbers */}
            <Row style={{ gap: 8, marginTop: 14 }}>
              {([[lang === 'fr' ? 'Moyenne' : 'Average', p.avg], [lang === 'fr' ? 'Dernier' : 'Last', p.last], [lang === 'fr' ? 'Meilleur' : 'Best', p.best], [lang === 'fr' ? 'Pire' : 'Worst', p.worst]] as const).map(([l, v]) => (
                <View key={l} style={s.tile}><Txt v="num" c={fpColor(v)} style={{ fontSize: 22 }}>{fpText(v)}</Txt><Txt v="label" style={{ fontSize: 9 }}>{l}</Txt></View>
              ))}
            </Row>
            <Txt v="small" style={{ marginTop: 8 }}>{lang === 'fr' ? 'Réel par match' : 'Real per game'} : {p.real.pts} {t('pts')} · {p.real.reb} {t('reb')} · {p.real.ast} {t('ast')} · {p.real.min} min · {p.owned}% {lang === 'fr' ? 'des équipes' : 'of teams'}</Txt>

            {/* where the points come from, per game on average */}
            <Txt v="label" style={{ marginTop: 18, marginBottom: 8 }}>{lang === 'fr' ? 'Points fantasy par match, en moyenne' : 'Fantasy points per game, on average'}</Txt>
            <View style={s.box}>
              {p.avg_breakdown.map((b, i) => <PartRow key={b.key} b={b} L={L} first={!i} />)}
              <Row style={{ paddingTop: 8, marginTop: 4, borderTopWidth: 1, borderColor: C.lineStrong }}>
                <Txt v="sub" c={C.txt} style={{ flex: 1, fontWeight: '800' }}>{lang === 'fr' ? 'Total' : 'Total'}</Txt>
                <Txt v="num" c={fpColor(p.avg)} style={{ fontSize: 20 }}>{fpText(p.avg)}</Txt>
              </Row>
            </View>

            {/* game by game */}
            <Txt v="label" style={{ marginTop: 18, marginBottom: 8 }}>{lang === 'fr' ? 'Match par match' : 'Game by game'}</Txt>
            {p.games.map(g => (
              <Pressable key={g.game_id} onPress={() => { tap(); setOpen(open === g.game_id ? null : g.game_id); }} style={[s.box, { marginBottom: 8 }]}>
                <Row style={{ gap: 10 }}>
                  <Txt v="label" style={{ width: 30 }}>J{g.md}</Txt>
                  <TeamLogo code={g.opp} size={26} />
                  <View style={{ flex: 1 }}>
                    <Txt v="sub" c={C.txt} numberOfLines={1}>{g.home === false ? '@ ' : ''}{g.opp} <Txt v="small" c={g.won ? C.good : C.bad}>{g.won ? (lang === 'fr' ? 'V' : 'W') : (lang === 'fr' ? 'D' : 'L')} {g.score}</Txt></Txt>
                    <Txt v="small" numberOfLines={1}>{g.played ? `${Math.round(g.line.min)}' · ${g.line.pts} ${t('pts')} · ${g.line.reb} ${t('reb')} · ${g.line.ast} ${t('ast')} · ${g.line.fgm}/${g.line.fga}` : (lang === 'fr' ? 'n’a pas joué' : 'did not play')} · {dayLabel(g.date, lang, { day: 'numeric', month: 'short' })}</Txt>
                  </View>
                  <View style={[s.fp, { borderColor: fpColor(g.fp) }]}><Txt v="num" c={fpColor(g.fp)} style={{ fontSize: 18 }}>{fpText(g.fp)}</Txt></View>
                  <Ionicons name={open === g.game_id ? 'chevron-up' : 'chevron-down'} size={14} color={C.mut} />
                </Row>
                {open === g.game_id && g.breakdown.length ? <View style={{ marginTop: 10 }}>{g.breakdown.map((b, i) => <PartRow key={b.key} b={b} L={L} first={!i} />)}</View> : null}
              </Pressable>
            ))}
          </ScrollView>
        )}
        {action ? (
          <Pressable disabled={action.disabled} onPress={() => { tap(); action.onPress(); }} style={[s.action, { backgroundColor: action.danger ? C.bad : C.orange, opacity: action.disabled ? 0.4 : 1 }]}>
            <Txt style={{ fontFamily: F.display, fontSize: 20, color: action.danger ? '#fff' : '#1A1205' }}>{action.label.toUpperCase()}</Txt>
          </Pressable>
        ) : null}
      </View>
    </Modal>
  );
}

function PartRow({ b, L, first }: { b: Part; L: (s: string) => string; first?: boolean }) {
  return (
    <Row style={{ paddingVertical: 5, borderTopWidth: first ? 0 : 1, borderColor: C.line }}>
      <Txt v="sub" style={{ flex: 1 }}>{L(b.label)}</Txt>
      <Txt v="small" style={{ width: 54, textAlign: 'right' }}>{b.key === 'double_double' || b.key === 'triple_double' ? '' : `× ${b.count}`}</Txt>
      <Txt v="sub" c={b.points < 0 ? C.bad : C.good} style={{ width: 64, textAlign: 'right', fontWeight: '700' }}>{fpText(b.points)}</Txt>
    </Row>
  );
}

const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(5,8,18,0.6)' },
  sheet: { maxHeight: '88%', backgroundColor: C.bg2, borderTopLeftRadius: R.xl, borderTopRightRadius: R.xl, borderWidth: 1, borderColor: C.line, paddingHorizontal: 16, paddingTop: 10 },
  tablet: { alignSelf: 'center', width: 620, marginBottom: 24, borderRadius: R.xl },
  grip: { alignSelf: 'center', width: 38, height: 4, borderRadius: 2, backgroundColor: C.lineStrong, marginBottom: 14 },
  price: { alignItems: 'center', backgroundColor: C.card2, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 },
  tile: { flex: 1, alignItems: 'center', backgroundColor: C.card, borderRadius: 14, paddingVertical: 10, borderWidth: 1, borderColor: C.line },
  box: { backgroundColor: C.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: C.line },
  fp: { minWidth: 58, alignItems: 'center', borderRadius: 10, borderWidth: 1.5, paddingVertical: 2 },
  action: { marginTop: 10, borderRadius: R.pill, paddingVertical: 14, alignItems: 'center' },
});
