import { LinearGradient } from 'expo-linear-gradient';
import { Pressable, View } from 'react-native';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { Avatar, tap, Txt } from '@/components/ui';
import { titleCase } from '@/lib/format';
import { C, F, R } from '@/theme';
import { FPlayer } from './types';

// A half court seen from above, the five starters on it (two guards out front, forwards on the wings, the centre under the rim), the bench below.
const SPOTS = [{ x: 0.3, y: 0.1 }, { x: 0.7, y: 0.1 }, { x: 0.15, y: 0.44 }, { x: 0.85, y: 0.44 }, { x: 0.5, y: 0.6 }];

export function Court({ starters, bench, captain, vice, points, onPress, width }: {
  starters: FPlayer[]; bench: FPlayer[]; captain?: string | null; vice?: string | null; points?: Record<string, { points: number; mult: number; played: boolean }>;
  onPress?: (p: FPlayer) => void; width: number;
}) {
  const h = Math.min(width * 0.82, 460);
  const order = ['G', 'G', 'F', 'F', 'C'];
  const placed: FPlayer[] = [];
  const left = [...starters];
  for (const pos of order) { const i = left.findIndex(p => p.pos === pos); if (i >= 0) placed.push(left.splice(i, 1)[0]); }
  placed.push(...left);
  return (
    <View>
      <View style={{ width: '100%', height: h, borderRadius: R.xl, overflow: 'hidden', borderWidth: 1, borderColor: C.lineStrong }}>
        <LinearGradient colors={['#2B1C46', '#1B1840', '#121733']} style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0 }} />
        <Svg width="100%" height="100%" viewBox="0 0 100 82" preserveAspectRatio="none" style={{ position: 'absolute' }}>
          <Rect x="2" y="2" width="96" height="78" fill="none" stroke="rgba(255,255,255,0.16)" strokeWidth="0.4" />
          <Rect x="33" y="52" width="34" height="28" fill="rgba(255,138,31,0.10)" stroke="rgba(255,138,31,0.55)" strokeWidth="0.4" />
          <Circle cx="50" cy="52" r="10" fill="none" stroke="rgba(255,138,31,0.55)" strokeWidth="0.4" />
          <Path d="M 8 80 L 8 66 A 42 42 0 0 1 92 66 L 92 80" fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth="0.45" />
          <Line x1="44" y1="76" x2="56" y2="76" stroke="rgba(255,255,255,0.5)" strokeWidth="0.6" />
          <Circle cx="50" cy="73.5" r="1.6" fill="none" stroke={C.orange} strokeWidth="0.5" />
          <Path d="M 38 2 A 12 12 0 0 0 62 2" fill="none" stroke="rgba(255,255,255,0.16)" strokeWidth="0.4" />
        </Svg>
        {placed.slice(0, 5).map((p, i) => (
          <Spot key={p.id} p={p} x={SPOTS[i].x} y={SPOTS[i].y} cap={p.id === captain} vice={p.id === vice} pts={points?.[p.id]} onPress={onPress} />
        ))}
      </View>
      {bench.length ? (
        <View style={{ flexDirection: 'row', gap: 10, marginTop: 12, backgroundColor: C.glass, borderRadius: R.lg, padding: 12, borderWidth: 1, borderColor: C.line }}>
          {bench.map((p, i) => (
            <Pressable key={p.id} onPress={() => { tap(); onPress?.(p); }} style={{ flex: 1, alignItems: 'center', gap: 4 }}>
              <Txt v="label" style={{ fontSize: 9 }}>{i + 1} · {p.pos}</Txt>
              <Avatar photo={p.photo} name={p.name} size={46} team={p.team} />
              <Txt v="small" c={C.txt} numberOfLines={1} style={{ fontWeight: '700' }}>{lastName(p.name)}</Txt>
              {points?.[p.id] ? <Badge v={points[p.id].mult ? points[p.id].points : points[p.id].points} dim={!points[p.id].mult} /> : <Txt v="small">{p.price.toFixed(1)}</Txt>}
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const lastName = (n: string) => { const s = titleCase(n).split(' '); return s.length > 1 ? s.slice(-1)[0] : s[0]; };

function Badge({ v, dim }: { v: number; dim?: boolean }) {
  return <View style={{ backgroundColor: dim ? C.glassStrong : C.orange, borderRadius: 99, paddingHorizontal: 8, paddingVertical: 1 }}><Txt style={{ fontFamily: F.display, fontSize: 15, color: dim ? C.sub : '#1A1205' }}>{v}</Txt></View>;
}

function Spot({ p, x, y, cap, vice, pts, onPress }: { p: FPlayer; x: number; y: number; cap?: boolean; vice?: boolean; pts?: { points: number; mult: number; played: boolean }; onPress?: (p: FPlayer) => void }) {
  return (
    <Pressable onPress={() => { tap(); onPress?.(p); }} style={{ position: 'absolute', left: `${x * 100}%`, top: `${y * 100}%`, width: 92, marginLeft: -46, alignItems: 'center', gap: 3 }}>
      <View>
        <Avatar photo={p.photo} name={p.name} size={58} team={p.team} />
        {cap || vice ? (
          <View style={{ position: 'absolute', left: -4, top: -4, width: 22, height: 22, borderRadius: 11, backgroundColor: cap ? C.amber : C.sub, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: C.bg }}>
            <Txt style={{ fontFamily: F.display, fontSize: 13, color: '#1A1205' }}>{cap ? 'C' : 'V'}</Txt>
          </View>
        ) : null}
      </View>
      <View style={{ backgroundColor: 'rgba(11,16,32,0.85)', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2, maxWidth: 92 }}>
        <Txt v="small" c={C.txt} numberOfLines={1} style={{ fontWeight: '700' }}>{lastName(p.name)}</Txt>
      </View>
      {pts ? <Badge v={pts.points} dim={!pts.played} /> : <Txt v="small" c={C.sub}>{p.next ? `${p.next.home ? '' : '@'}${p.next.code}` : p.price.toFixed(1)}</Txt>}
    </Pressable>
  );
}
