import { Ionicons } from '@expo/vector-icons';
import { useMemo, useState } from 'react';
import { Pressable, TextInput, View } from 'react-native';

import { Avatar, Card, Chips, HeroCard, Row, Segmented, tap, Txt, useLayout } from '@/components/ui';
import { postJSON } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { titleCase } from '@/lib/format';
import { C, F, GRAD, R } from '@/theme';
import { Court } from './Court';
import { fpColor, fpText, PlayerSheet } from './PlayerSheet';
import { Chip, Config, FPlayer, Pick, Pos } from './types';

type Sort = 'price' | 'avg' | 'form' | 'owned';
const CHIP_ICON: Record<Chip, keyof typeof Ionicons.glyphMap> = { triple_captain: 'flash', bench_boost: 'people', wildcard: 'shuffle', all_star: 'star' };

export function Builder({ cfg, pool, start, chipsLeft, isNew, onSaved }: { cfg: Config; pool: FPlayer[]; start?: Pick | null; chipsLeft: Chip[]; isNew: boolean; onSaved: () => void }) {
  const { t, vid, lang } = useApp();
  const { width, tablet } = useLayout();
  const by = useMemo(() => Object.fromEntries(pool.map(p => [p.id, p])), [pool]);
  const [step, setStep] = useState<'squad' | 'lineup'>(start ? 'lineup' : 'squad');
  const [squad, setSquad] = useState<string[]>(start?.squad.filter(id => by[id]) || []);
  const [starters, setStarters] = useState<string[]>(start?.starters || []);
  const [captain, setCaptain] = useState<string | null>(start?.captain || null);
  const [vice, setVice] = useState<string | null>(start?.vice || null);
  const [chip, setChip] = useState<Chip | null>(null);
  const [pos, setPos] = useState<'all' | Pos>('all');
  const [sort, setSort] = useState<Sort>('avg');
  const [q, setQ] = useState('');
  const [name, setName] = useState('');
  const [teamName, setTeamName] = useState('');
  const [md, setMd] = useState<number | null>(cfg.test ? cfg.open_md : null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sheet, setSheet] = useState<string | null>(null);

  const cost = squad.reduce((s, id) => s + (by[id]?.price || 0), 0);
  const budget = chip === 'all_star' ? 999 : cfg.budget;
  const count = (k: Pos) => squad.filter(id => by[id]?.pos === k).length;
  const club = (c: string) => squad.filter(id => by[id]?.team === c).length;
  const full = squad.length === 8;
  const why = (p: FPlayer) => squad.includes(p.id) ? null : count(p.pos) >= cfg.squad[p.pos] ? 'pos' : club(p.team) >= cfg.max_per_club ? 'club' : cost + p.price > budget + 1e-6 ? 'money' : null;

  const list = useMemo(() => pool
    .filter(p => (pos === 'all' || p.pos === pos) && (!q || p.name.toLowerCase().includes(q.toLowerCase()) || p.team.toLowerCase() === q.toLowerCase()))
    .sort((a, b) => b[sort] - a[sort]).slice(0, 80), [pool, pos, sort, q]);

  const toggle = (p: FPlayer) => {
    tap();
    if (squad.includes(p.id)) { setSquad(squad.filter(x => x !== p.id)); setStarters(starters.filter(x => x !== p.id)); if (captain === p.id) setCaptain(null); if (vice === p.id) setVice(null); return; }
    if (!why(p)) setSquad([...squad, p.id]);
  };
  const toggleStart = (id: string) => {
    tap();
    if (starters.includes(id)) { setStarters(starters.filter(x => x !== id)); if (captain === id) setCaptain(null); if (vice === id) setVice(null); }
    else if (starters.length < 5) setStarters([...starters, id]);
  };
  const lineupOk = starters.length === 5 && (['G', 'F', 'C'] as Pos[]).every(k => starters.some(id => by[id]?.pos === k)) && !!captain;

  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      await postJSON('/api/fantasy/team', { vid, squad, starters, captain, vice, chip, md: cfg.test ? md : undefined, name: name || undefined, team_name: teamName || undefined });
      setMsg(t('fSaved')); onSaved();
    } catch (e) {
      const errs = (e as { data?: { errors?: string[] } }).data?.errors;
      setMsg(errs?.join(' · ') || String(e));
    } finally { setBusy(false); }
  };

  const spent = Math.min(1, cost / cfg.budget);
  return (
    <View>
      {/* budget */}
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <View><Txt v="label">{t('fBudget')}</Txt><Txt v="numL">{cost.toFixed(1)} <Txt v="sub">/ {chip === 'all_star' ? '∞' : cfg.budget}</Txt></Txt></View>
          <Row style={{ gap: 12 }}>
            {(['G', 'F', 'C'] as Pos[]).map(k => (
              <View key={k} style={{ alignItems: 'center' }}><Txt v="num" c={count(k) === cfg.squad[k] ? C.good : C.txt}>{count(k)}/{cfg.squad[k]}</Txt><Txt v="label">{k}</Txt></View>
            ))}
          </Row>
        </Row>
        <View style={{ height: 8, borderRadius: 4, backgroundColor: C.glass, marginTop: 10 }}><View style={{ width: `${spent * 100}%`, height: 8, borderRadius: 4, backgroundColor: cost > cfg.budget ? C.bad : C.orange }} /></View>
        <Txt v="small" style={{ marginTop: 6 }}>{(cfg.budget - cost).toFixed(1)} {t('fLeft')} · max {cfg.max_per_club} / club</Txt>
      </Card>

      <View style={{ marginTop: 12 }}>
        <Segmented<'squad' | 'lineup'> value={step} onChange={v => (v === 'lineup' && !full ? null : setStep(v))} items={[{ key: 'squad', label: `1 · ${t('fTransfers')}` }, { key: 'lineup', label: `2 · ${t('fMyTeam')}` }]} />
      </View>

      {step === 'squad' ? (
        <View style={{ marginTop: 12, gap: 10 }}>
          {squad.length ? (
            <Row style={{ flexWrap: 'wrap', gap: 8 }}>
              {squad.map(id => by[id] && (
                <Pressable key={id} onPress={() => toggle(by[id])} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.card2, borderRadius: R.pill, paddingLeft: 4, paddingRight: 10, paddingVertical: 4, borderWidth: 1, borderColor: C.line }}>
                  <Avatar photo={by[id].photo} name={by[id].name} size={26} />
                  <Txt v="small" c={C.txt} style={{ fontWeight: '700' }}>{titleCase(by[id].name).split(' ').slice(-1)[0]}</Txt>
                  <Ionicons name="close" size={14} color={C.mut} />
                </Pressable>
              ))}
            </Row>
          ) : null}
          <Row style={{ backgroundColor: C.glass, borderRadius: R.pill, borderWidth: 1, borderColor: C.line, paddingHorizontal: 14, gap: 8 }}>
            <Ionicons name="search" size={16} color={C.mut} />
            <TextInput value={q} onChangeText={setQ} placeholder={t('search')} placeholderTextColor={C.mut} style={{ flex: 1, color: C.txt, paddingVertical: 10 }} autoCorrect={false} />
          </Row>
          <Chips<'all' | Pos> value={pos} onChange={setPos} items={[{ key: 'all', label: t('all') }, { key: 'G', label: t('fG') }, { key: 'F', label: t('fF') }, { key: 'C', label: t('fC') }]} />
          <Chips<Sort> value={sort} onChange={setSort} items={[{ key: 'avg', label: lang === 'fr' ? 'Moy. fantasy' : 'Fantasy avg' }, { key: 'form', label: t('form') }, { key: 'price', label: lang === 'fr' ? 'Prix' : 'Price' }, { key: 'owned', label: lang === 'fr' ? 'Sélectionné %' : 'Selected %' }]} />
          <Card padded={false}>
            {list.map((p, i) => {
              const inSquad = squad.includes(p.id), w = why(p);
              return (
                <Pressable key={p.id} onPress={() => { tap(); setSheet(p.id); }}>
                  <Row style={{ paddingHorizontal: 12, paddingVertical: 10, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line, backgroundColor: inSquad ? 'rgba(255,138,31,0.08)' : undefined }}>
                    <View style={{ opacity: !inSquad && w ? 0.45 : 1 }}><Avatar photo={p.photo} name={p.name} size={40} team={p.team} /></View>
                    <View style={{ flex: 1, opacity: !inSquad && w ? 0.45 : 1 }}>
                      <Txt v="sub" c={C.txt} style={{ fontWeight: '700' }} numberOfLines={1}>{titleCase(p.name)}</Txt>
                      <Txt v="small" numberOfLines={1}>{p.pos} · {p.team}{p.next ? ` · ${p.next.home ? 'vs' : '@'} ${p.next.code}` : ''} · {p.owned}%</Txt>
                      <Txt v="small" c={C.sub} numberOfLines={1}>{(p.pts ?? 0).toFixed(1)} {t('pts')} · {lang === 'fr' ? 'dernier' : 'last'} <Txt v="small" c={fpColor(p.last)} style={{ fontWeight: '700' }}>{fpText(p.last)}</Txt></Txt>
                    </View>
                    <View style={{ alignItems: 'center', width: 52 }}>
                      <Txt v="num" c={fpColor(p.avg)} style={{ fontSize: 19 }}>{fpText(p.avg)}</Txt>
                      <Txt v="label" style={{ fontSize: 8 }}>{lang === 'fr' ? 'MOY. FANTASY' : 'FANTASY AVG'}</Txt>
                    </View>
                    <View style={{ backgroundColor: C.card2, borderRadius: 8, paddingHorizontal: 7, paddingVertical: 4, minWidth: 44, alignItems: 'center' }}><Txt v="num" c={C.amber} style={{ fontSize: 16 }}>{p.price.toFixed(1)}</Txt></View>
                    <Pressable onPress={() => toggle(p)} disabled={!inSquad && !!w} hitSlop={10}>
                      <Ionicons name={inSquad ? 'remove-circle' : 'add-circle'} size={28} color={inSquad ? C.bad : w ? C.mut : C.orange} />
                    </Pressable>
                  </Row>
                </Pressable>
              );
            })}
          </Card>
        </View>
      ) : (
        <View style={{ marginTop: 12, gap: 12 }}>
          <Court width={Math.min(width - 32, tablet ? 640 : 999)} starters={starters.map(id => by[id]).filter(Boolean)} bench={squad.filter(id => !starters.includes(id)).map(id => by[id]).filter(Boolean)} captain={captain} vice={vice} onPress={p => setSheet(p.id)} />
          <Txt v="small">{lang === 'fr' ? 'Touche « 5 » pour titulariser (au moins un meneur/arrière, un ailier, un pivot), puis C et V.' : 'Tap "5" to start a player (at least one guard, one forward, one centre), then C and V.'}</Txt>
          <Card padded={false}>
            {squad.map((id, i) => by[id] && (
              <Row key={id} style={{ paddingHorizontal: 12, paddingVertical: 9, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                <Avatar photo={by[id].photo} name={by[id].name} size={36} />
                <View style={{ flex: 1 }}><Txt v="sub" c={C.txt} style={{ fontWeight: '700' }} numberOfLines={1}>{titleCase(by[id].name)}</Txt><Txt v="small">{by[id].pos} · {by[id].team} · {by[id].avg.toFixed(1)}</Txt></View>
                <Toggle on={starters.includes(id)} label="5" onPress={() => toggleStart(id)} />
                <Toggle on={captain === id} label="C" gold disabled={!starters.includes(id)} onPress={() => { tap(); setCaptain(id); if (vice === id) setVice(null); }} />
                <Toggle on={vice === id} label="V" disabled={!starters.includes(id) || captain === id} onPress={() => { tap(); setVice(id); }} />
              </Row>
            ))}
          </Card>

          <Txt v="h2" style={{ marginTop: 6 }}>{t('fChips')}</Txt>
          <Row style={{ flexWrap: 'wrap', gap: 10 }}>
            {cfg.chips.map(c => {
              const can = chipsLeft.includes(c) || start?.chip === c, on = chip === c;
              return (
                <Pressable key={c} disabled={!can} onPress={() => { tap(); setChip(on ? null : c); }} style={{ width: tablet ? '23.5%' : '48%', opacity: can ? 1 : 0.35 }}>
                  <View style={{ borderRadius: R.lg, padding: 12, borderWidth: 1.5, borderColor: on ? C.amber : C.line, backgroundColor: on ? 'rgba(255,181,71,0.12)' : C.card }}>
                    <Ionicons name={CHIP_ICON[c]} size={22} color={on ? C.amber : C.sub} />
                    <Txt v="h3" style={{ marginTop: 6 }}>{t(c)}</Txt>
                    <Txt v="small" numberOfLines={3}>{t(`${c}D` as never)}</Txt>
                  </View>
                </Pressable>
              );
            })}
          </Row>

          {isNew ? (
            <Card style={{ gap: 8 }}>
              <TextInput value={name} onChangeText={setName} placeholder={t('fYourName')} placeholderTextColor={C.mut} maxLength={24} style={{ color: C.txt, borderBottomWidth: 1, borderColor: C.line, paddingVertical: 8 }} />
              <TextInput value={teamName} onChangeText={setTeamName} placeholder={t('fTeamName')} placeholderTextColor={C.mut} maxLength={30} style={{ color: C.txt, paddingVertical: 8 }} />
            </Card>
          ) : null}

          {cfg.test ? (
            <Card glow="rgba(91,140,255,0.6)">
              <Txt v="label" c={C.blue}>{t('fTest')}</Txt>
              <View style={{ marginTop: 8 }}>
                <Chips<string> value={String(md)} onChange={v => setMd(Number(v))} items={cfg.matchdays.map(m => ({ key: String(m.md), label: `J${m.md}${m.done ? ' ✓' : ''}` }))} />
              </View>
            </Card>
          ) : null}

          <HeroCard colors={lineupOk ? GRAD.hero : ['#2A3150', '#2A3150']} onPress={lineupOk && !busy ? save : undefined} style={{ paddingVertical: 16, alignItems: 'center' }}>
            <Txt style={{ fontFamily: F.display, fontSize: 24, color: '#fff' }}>{busy ? '…' : t('fSave').toUpperCase()}</Txt>
          </HeroCard>
          {msg ? <Txt v="sub" c={msg === t('fSaved') ? C.good : C.bad} style={{ textAlign: 'center' }}>{msg}</Txt> : null}
        </View>
      )}
      {sheet && by[sheet] ? (
        <PlayerSheet id={sheet} onClose={() => setSheet(null)} action={squad.includes(sheet)
          ? { label: lang === 'fr' ? 'Retirer de mon équipe' : 'Remove from my team', danger: true, onPress: () => { toggle(by[sheet]); setSheet(null); } }
          : { label: why(by[sheet]) ? (why(by[sheet]) === 'money' ? (lang === 'fr' ? 'Budget dépassé' : 'Over budget') : why(by[sheet]) === 'club' ? (lang === 'fr' ? '3 joueurs de ce club déjà' : '3 players of this club already') : (lang === 'fr' ? 'Poste complet' : 'Position full')) : (lang === 'fr' ? 'Ajouter à mon équipe' : 'Add to my team'),
              disabled: !!why(by[sheet]), onPress: () => { toggle(by[sheet]); setSheet(null); } }} />
      ) : null}
      {step === 'squad' && full ? (
        <HeroCard colors={GRAD.hero} onPress={() => setStep('lineup')} style={{ marginTop: 14, paddingVertical: 16, alignItems: 'center' }}>
          <Txt style={{ fontFamily: F.display, fontSize: 22, color: '#fff' }}>{lang === 'fr' ? 'SUIVANT : MON CINQ ›' : 'NEXT: MY FIVE ›'}</Txt>
        </HeroCard>
      ) : null}
    </View>
  );
}

function Toggle({ on, label, onPress, gold, disabled }: { on: boolean; label: string; onPress: () => void; gold?: boolean; disabled?: boolean }) {
  return (
    <Pressable disabled={disabled} onPress={onPress} style={{ width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, opacity: disabled ? 0.3 : 1,
      borderColor: on ? (gold ? C.amber : C.orange) : C.lineStrong, backgroundColor: on ? (gold ? C.amber : C.orange) : 'transparent' }}>
      <Txt style={{ fontFamily: F.display, fontSize: 16, color: on ? '#1A1205' : C.sub }}>{label}</Txt>
    </Pressable>
  );
}
