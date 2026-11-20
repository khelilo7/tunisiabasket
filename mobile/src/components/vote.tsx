import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { postJSON } from '@/lib/api';
import { C, R } from '@/theme';
import { tap, Txt } from './ui';

// Shared pieces of the fan votes (predictions, player of the round, phase MVP, play of the week). Every vote is final and anonymous (the device's id).

export function closesIn(ts: number | null | undefined, fr: boolean) {
  if (!ts) return '';
  const s = ts - Date.now() / 1000;
  if (s <= 0) return fr ? 'terminé' : 'ended';
  const d = Math.floor(s / 86400), h = Math.floor(s / 3600), m = Math.max(1, Math.floor(s / 60));
  const v = d >= 1 ? `${d} ${fr ? 'j' : 'd'}` : h >= 1 ? `${h} h` : `${m} min`;
  return fr ? `fin dans ${v}` : `ends in ${v}`;
}

export function voteError(e: unknown, fr: boolean) {
  const why = (e as { data?: { reason?: string } })?.data?.reason;
  if (why === 'already') return fr ? 'Tu as déjà voté.' : 'You already voted.';
  if (why === 'closed') return fr ? 'Le vote est terminé.' : 'Voting is over.';
  if (why === 'network') return fr ? 'Trop de votes depuis ce réseau. Réessaie en 4G ou sur un autre Wi-Fi.' : 'Too many votes from this network. Try on mobile data or another Wi-Fi.';
  return fr ? 'Le vote n’a pas pu être enregistré. Réessaie.' : 'Your vote could not be saved. Try again.';
}

// Post a vote: busy state, the error in plain words, then `done` (a refresh of the screen's data).
export function useVote(path: string, done: () => void, fr: boolean) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState('');
  const send = async (id: string, body: object) => {
    if (busy) return;
    tap(); setBusy(id); setErr('');
    try { await postJSON(path, body); } catch (e) { setErr(voteError(e, fr)); }
    setBusy(null); done();
  };
  return { busy, err, send };
}

export function VoteBtn({ onPress, busy, label }: { onPress: () => void; busy?: boolean; label: string }) {
  return (
    <Pressable onPress={onPress} disabled={busy} style={({ pressed }) => [s.btn, pressed && { opacity: 0.8 }]} hitSlop={4}>
      {busy ? <ActivityIndicator size="small" color="#1A1205" /> : <Txt v="small" c="#1A1205" style={{ fontWeight: '800', fontSize: 13 }}>{label}</Txt>}
    </Pressable>
  );
}

export function ShareBar({ share, mine, lead }: { share: number; mine?: boolean; lead?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <View style={s.track}><View style={[s.fill, { width: `${Math.max(2, share)}%`, backgroundColor: mine ? C.orange : lead ? C.amber : C.lineStrong }]} /></View>
      <Txt v="small" c={mine ? C.orange : C.sub} style={{ fontWeight: '800', minWidth: 36, textAlign: 'right' }}>{Math.round(share)}%</Txt>
    </View>
  );
}

export function MineTag({ fr }: { fr: boolean }) {
  return (
    <View style={s.mine}><Ionicons name="checkmark-circle" size={13} color={C.orange} /><Txt v="small" c={C.orange} style={{ fontWeight: '800' }}>{fr ? 'Ton vote' : 'Your vote'}</Txt></View>
  );
}

export function ErrLine({ text }: { text: string }) {
  return text ? <Txt v="small" c={C.bad} style={{ marginTop: 8 }}>{text}</Txt> : null;
}

const s = StyleSheet.create({
  btn: { backgroundColor: C.orange, borderRadius: R.pill, paddingHorizontal: 16, height: 34, minWidth: 74, alignItems: 'center', justifyContent: 'center' },
  track: { flex: 1, height: 6, borderRadius: 3, backgroundColor: C.glass, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3 },
  mine: { flexDirection: 'row', alignItems: 'center', gap: 3 },
});
