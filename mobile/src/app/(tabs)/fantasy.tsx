import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, TextInput, View } from 'react-native';

import { Avatar, Card, Chips, Empty, HeroCard, Loading, Row, Screen, Section, tap, Txt, useLayout } from '@/components/ui';
import { FANTASY_ON, postJSON, useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { titleCase } from '@/lib/format';
import { C, F, GRAD, R } from '@/theme';
import { Builder } from '@/fantasy/Builder';
import { Court } from '@/fantasy/Court';
import { PlayerSheet } from '@/fantasy/PlayerSheet';
import { Config, FPlayer, Hist, Me, RankRow } from '@/fantasy/types';

type Tab = 'team' | 'build' | 'ranking' | 'leagues' | 'rules';
const GRADE_C: Record<string, string> = { 'A+': '#3ECF8E', A: '#7BD88F', B: '#FFB547', C: '#FF8A1F', D: '#FF5D6C' };

export default function Fantasy() {
  const { t, vid } = useApp();
  const cfg = useApi<Config>(FANTASY_ON ? '/api/fantasy/config' : null);
  const pool = useApi<{ players: FPlayer[] }>(FANTASY_ON ? '/api/fantasy/pool' : null);
  const me = useApi<Me>(FANTASY_ON && vid ? `/api/fantasy/me?vid=${vid}` : null);
  const [tab, setTab] = useState<Tab>('team');
  const reload = () => { me.refresh(); pool.refresh(); cfg.refresh(); };

  if (!FANTASY_ON) return <Screen><Empty text={t('fHidden')} /></Screen>;
  if (!cfg.data || !pool.data || !me.data) return <Screen>{cfg.error ? <Empty text={`${t('offline')} (FANTASY=1 ?)`} /> : <Loading />}</Screen>;
  const e = me.data.entry;

  return (
    <Screen onRefresh={reload} refreshing={me.refreshing}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <View>
          <Txt v="label" c={C.amber}>Pro A</Txt>
          <Txt v="h1">Fantasy</Txt>
        </View>
        {cfg.data.test ? <View style={{ backgroundColor: 'rgba(91,140,255,0.18)', borderRadius: 99, paddingHorizontal: 10, paddingVertical: 4 }}><Txt v="small" c={C.blue} style={{ fontWeight: '800' }}>TEST</Txt></View> : null}
      </Row>
      {!e && tab !== 'build' && tab !== 'rules' ? (
        <Welcome onStart={() => setTab('build')} cfg={cfg.data} />
      ) : (
        <>
          <View style={{ marginTop: 12 }}>
            <Chips<Tab> value={tab} onChange={setTab} items={[
              { key: 'team', label: t('fMyTeam') }, { key: 'build', label: t('fTransfers') }, { key: 'ranking', label: t('fRanking') }, { key: 'leagues', label: t('fLeagues') }, { key: 'rules', label: t('fRules') },
            ]} />
          </View>
          <View style={{ marginTop: 14 }}>
            {tab === 'team' && e ? <Dashboard me={me.data} cfg={cfg.data} pool={pool.data.players} onEdit={() => setTab('build')} /> : null}
            {tab === 'build' ? <Builder cfg={cfg.data} pool={pool.data.players} start={e?.current} chipsLeft={e?.chips_left || cfg.data.chips} isNew={!e} onSaved={() => { reload(); setTimeout(() => setTab('team'), 600); }} /> : null}
            {tab === 'ranking' ? <Ranking /> : null}
            {tab === 'leagues' ? <Leagues me={me.data} onChange={reload} /> : null}
            {tab === 'rules' ? <Rules cfg={cfg.data} /> : null}
          </View>
        </>
      )}
    </Screen>
  );
}

function Welcome({ onStart, cfg }: { onStart: () => void; cfg: Config }) {
  const { t } = useApp();
  return (
    <View style={{ marginTop: 16, gap: 14 }}>
      <HeroCard colors={GRAD.violet}>
        <Ionicons name="trophy" size={40} color="#FFD27A" />
        <Txt style={{ fontFamily: F.display, fontSize: 36, lineHeight: 38, color: '#fff', marginTop: 10 }}>{t('fWelcome').toUpperCase()}</Txt>
        <Txt v="sub" c="rgba(255,255,255,0.9)" style={{ marginTop: 8 }}>{t('fWelcomeText')}</Txt>
        <Pressable onPress={() => { tap(); onStart(); }} style={{ marginTop: 18, backgroundColor: '#fff', borderRadius: R.pill, paddingVertical: 14, alignItems: 'center' }}>
          <Txt style={{ fontFamily: F.display, fontSize: 22, color: '#3A2A9C' }}>{t('fStart').toUpperCase()}</Txt>
        </Pressable>
      </HeroCard>
      <Row style={{ gap: 10 }}>
        {([['people', '8', t('players')], ['wallet', String(cfg.budget), t('fBudget')], ['star', 'x2', t('fCaptain')]] as const).map(([i, v, l]) => (
          <Card key={l} style={{ flex: 1, alignItems: 'center' }}><Ionicons name={i} size={20} color={C.amber} /><Txt v="numL">{v}</Txt><Txt v="small" style={{ textAlign: 'center' }}>{l}</Txt></Card>
        ))}
      </Row>
      <Deadline cfg={cfg} />
    </View>
  );
}

function Deadline({ cfg }: { cfg: Config }) {
  const { t, lang } = useApp();
  const m = cfg.matchdays.find(x => x.md === cfg.open_md);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  if (!m) return null;
  const left = Math.max(0, m.deadline_ts * 1000 - now);
  const d = Math.floor(left / 864e5), h = Math.floor(left / 36e5) % 24, mi = Math.floor(left / 6e4) % 60, s = Math.floor(left / 1e3) % 60;
  return (
    <Card>
      <Row style={{ justifyContent: 'space-between', gap: 8 }}>
        <View style={{ flex: 1 }}><Txt v="label">{t('fDeadline')} · {t('matchday')} {m.md}</Txt><Txt v="small">{new Date(m.deadline).toLocaleString(lang === 'fr' ? 'fr-FR' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}</Txt></View>
        <Row style={{ gap: 5 }}>
          {[[d, lang === 'fr' ? 'J' : 'D'], [h, 'H'], [mi, 'M'], [s, 'S']].map(([v, l]) => (
            <View key={String(l)} style={{ alignItems: 'center', backgroundColor: C.card2, borderRadius: 10, paddingHorizontal: 5, paddingVertical: 4, minWidth: 32 }}>
              <Txt v="num" c={C.amber} style={{ fontSize: 20 }}>{String(v).padStart(2, '0')}</Txt><Txt v="label" style={{ fontSize: 8 }}>{l}</Txt>
            </View>
          ))}
        </Row>
      </Row>
    </Card>
  );
}

function Dashboard({ me, cfg, pool, onEdit }: { me: Me; cfg: Config; pool: FPlayer[]; onEdit: () => void }) {
  const { t, lang } = useApp();
  const { width, tablet } = useLayout();
  const e = me.entry!;
  const played = e.history.filter(h => !h.upcoming);
  const [sel, setSel] = useState<number | null>(null);
  const [sheet, setSheet] = useState<string | null>(null);
  const scored = played.filter(h => h.grade);                      // matchdays whose box scores are in (a matchday still waiting for them shows 0)
  const cur: Hist | undefined = played.find(h => h.md === sel) || scored[scored.length - 1] || played[played.length - 1];
  const by = useMemo(() => Object.fromEntries(pool.map(p => [p.id, p])), [pool]);
  const dream = useApi<{ team: (FPlayer & { points: number })[] }>(cur ? `/api/fantasy/dream/${cur.md}` : null);
  const pick = e.current;
  const max = Math.max(1, ...played.map(h => h.points || 0));

  const rows = cur?.rows || [];
  const pts = Object.fromEntries(rows.map(r => [r.id, { points: r.points || r.base, mult: r.mult, played: r.played }]));
  const shownSquad = cur ? rows.map(r => by[r.id]).filter(Boolean) : (pick?.squad || []).map(id => by[id]).filter(Boolean);
  const shownStarters = cur ? rows.filter(r => r.starter).map(r => by[r.id]).filter(Boolean) : (pick?.starters || []).map(id => by[id]).filter(Boolean);

  return (
    <View style={{ gap: 14 }}>
      <HeroCard colors={GRAD.violet}>
        <Row style={{ justifyContent: 'space-between' }}>
          <View style={{ flex: 1 }}>
            <Txt v="label" c="rgba(255,255,255,0.8)">{e.name || '—'}</Txt>
            <Txt style={{ fontFamily: F.display, fontSize: 28, color: '#fff' }} numberOfLines={1}>{(e.team_name || t('fMyTeam')).toUpperCase()}</Txt>
          </View>
          {cur?.grade ? (
            <View style={{ width: 64, height: 64, borderRadius: 20, backgroundColor: 'rgba(0,0,0,0.25)', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: GRADE_C[cur.grade] }}>
              <Txt style={{ fontFamily: F.display, fontSize: 32, color: GRADE_C[cur.grade] }}>{cur.grade}</Txt>
            </View>
          ) : null}
        </Row>
        <Row style={{ gap: 22, marginTop: 14 }}>
          <View><Txt v="label" c="rgba(255,255,255,0.75)">{t('fTotal')}</Txt><Txt style={{ fontFamily: F.display, fontSize: 44, lineHeight: 46, color: '#fff' }}>{e.total}</Txt></View>
          <View><Txt v="label" c="rgba(255,255,255,0.75)">{t('rank')}</Txt><Txt style={{ fontFamily: F.display, fontSize: 44, lineHeight: 46, color: '#fff' }}>{e.rank ?? '–'}<Txt style={{ fontFamily: F.display, fontSize: 20, color: 'rgba(255,255,255,0.7)' }}>/{e.of}</Txt></Txt></View>
          {cur ? <View><Txt v="label" c="rgba(255,255,255,0.75)">J{cur.md}</Txt><Txt style={{ fontFamily: F.display, fontSize: 44, lineHeight: 46, color: '#FFD27A' }}>{cur.points}</Txt></View> : null}
        </Row>
      </HeroCard>

      <Deadline cfg={cfg} />

      {played.length ? (
        <Card>
          <Txt v="label" style={{ marginBottom: 10 }}>{t('matchday')}</Txt>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, alignItems: 'flex-end' }}>
            {played.map(h => {
              const on = h.md === cur?.md;
              return (
                <Pressable key={h.md} onPress={() => { tap(); setSel(h.md); }} style={{ alignItems: 'center', width: 36 }}>
                  <Txt v="small" c={on ? C.txt : C.mut} style={{ fontSize: 10 }}>{h.points}</Txt>
                  <View style={{ width: 22, height: 8 + 70 * ((h.points || 0) / max), borderRadius: 6, backgroundColor: h.grade ? GRADE_C[h.grade] : C.glassStrong, opacity: on ? 1 : 0.55 }} />
                  <Txt v="label" c={on ? C.orange : C.mut} style={{ fontSize: 10, marginTop: 4 }}>J{h.md}</Txt>
                </Pressable>
              );
            })}
          </ScrollView>
        </Card>
      ) : null}

      {cur ? (
        <Row style={{ gap: 10 }}>
          {([[t('fPoints'), cur.points], ['Ø', cur.avg], [t('fBest'), cur.best], [t('rank'), cur.rank ? `${cur.rank}/${cur.of}` : '–']] as const).map(([l, v]) => (
            <Card key={String(l)} style={{ flex: 1, alignItems: 'center', paddingVertical: 12 }}><Txt v="num">{v ?? '–'}</Txt><Txt v="label" style={{ fontSize: 9 }}>{l}</Txt></Card>
          ))}
        </Row>
      ) : null}

      <Court width={Math.min(width - 32, tablet ? 640 : 999)} starters={shownStarters} bench={shownSquad.filter(p => !shownStarters.includes(p))}
        captain={cur?.captain ?? pick?.captain} vice={cur ? null : pick?.vice} points={cur ? pts : undefined} onPress={p => setSheet(p.id)} />
      {sheet ? <PlayerSheet id={sheet} onClose={() => setSheet(null)} /> : null}
      {cur?.subs?.length ? <Txt v="small">🔁 {cur.subs.map(s => `${titleCase(by[s.out]?.name || s.out)} → ${titleCase(by[s.in]?.name || s.in)}`).join(' · ')} ({t('fAutoSub')})</Txt> : null}
      {cur?.chip ? <Txt v="small" c={C.amber}>⚡ {t(cur.chip)}</Txt> : null}
      {cur && cur.hit ? <Txt v="small" c={C.bad}>−{cur.hit} {t('fHit')}</Txt> : null}

      <Row style={{ gap: 10 }}>
        <Pressable onPress={() => { tap(); onEdit(); }} style={{ flex: 1, backgroundColor: C.orange, borderRadius: R.pill, paddingVertical: 14, alignItems: 'center' }}>
          <Txt style={{ fontFamily: F.display, fontSize: 20, color: '#1A1205' }}>{t('fTransfers').toUpperCase()} · {e.free_transfers} {lang === 'fr' ? 'GRATUITS' : 'FREE'}</Txt>
        </Pressable>
      </Row>
      <Row style={{ gap: 8, flexWrap: 'wrap' }}>
        {cfg.chips.map(c => (
          <View key={c} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 99, backgroundColor: e.chips_left.includes(c) ? 'rgba(255,181,71,0.14)' : C.glass, borderWidth: 1, borderColor: e.chips_left.includes(c) ? 'rgba(255,181,71,0.5)' : C.line }}>
            <Txt v="small" c={e.chips_left.includes(c) ? C.amber : C.mut} style={{ fontWeight: '700', textDecorationLine: e.chips_left.includes(c) ? 'none' : 'line-through' }}>{t(c)}</Txt>
          </View>
        ))}
      </Row>

      {dream.data?.team?.length ? (
        <Section title={`${t('fDream')} · J${cur?.md}`}>
          <Card padded={false}>
            {dream.data.team.map((p, i) => (
              <Row key={p.id} style={{ paddingHorizontal: 12, paddingVertical: 10, gap: 10, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                <Txt v="num" c={i === 0 ? C.amber : C.mut} style={{ width: 20, fontSize: 18 }}>{i + 1}</Txt>
                <Avatar photo={p.photo} name={p.name} size={38} team={p.team} />
                <View style={{ flex: 1 }}><Txt v="sub" c={C.txt} style={{ fontWeight: '700' }}>{titleCase(p.name)}</Txt><Txt v="small">{p.pos} · {p.team}</Txt></View>
                <Txt v="num" c={C.orange}>{p.points}</Txt>
              </Row>
            ))}
          </Card>
        </Section>
      ) : null}
    </View>
  );
}

function Ranking({ league }: { league?: string }) {
  const { t, vid } = useApp();
  const { data } = useApi<{ rows: RankRow[] }>(`/api/fantasy/ranking${league ? `?league=${league}` : ''}`);
  if (!data) return <Loading />;
  if (!data.rows.length) return <Empty text={t('empty')} />;
  return (
    <Card padded={false}>
      {data.rows.map((r, i) => {
        const mine = vid.endsWith(r.me_key);
        return (
          <Row key={i} style={{ paddingHorizontal: 14, paddingVertical: 12, gap: 12, borderTopWidth: i ? 1 : 0, borderColor: C.line, backgroundColor: mine ? 'rgba(255,138,31,0.10)' : undefined }}>
            <Txt v="num" c={r.rank <= 3 ? C.amber : C.sub} style={{ width: 30, fontSize: 19 }}>{r.rank}</Txt>
            <View style={{ flex: 1 }}><Txt v="sub" c={C.txt} style={{ fontWeight: '700' }}>{r.team || r.name}</Txt><Txt v="small">{r.name}</Txt></View>
            <Txt v="num" c={mine ? C.orange : C.txt}>{r.total}</Txt>
          </Row>
        );
      })}
    </Card>
  );
}

function Leagues({ me, onChange }: { me: Me; onChange: () => void }) {
  const { t, vid } = useApp();
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const act = async (body: object) => {
    try { const r = await postJSON<{ code: string }>('/api/fantasy/league', { vid, ...body }); setMsg(`${t('fCode')}: ${r.code}`); onChange(); }
    catch (e) { setMsg(((e as { data?: { errors?: string[] } }).data?.errors || ['?']).join(' ')); }
  };
  const mine = me.entry?.leagues || [];
  return (
    <View style={{ gap: 12 }}>
      <Card style={{ gap: 10 }}>
        <Txt v="label">{t('fCreateLeague')}</Txt>
        <Row style={{ gap: 8 }}>
          <TextInput value={name} onChangeText={setName} placeholder="Les copains de Radès" placeholderTextColor={C.mut} style={{ flex: 1, color: C.txt, backgroundColor: C.glass, borderRadius: R.md, paddingHorizontal: 12, paddingVertical: 10 }} />
          <Pressable onPress={() => act({ action: 'create', name })} style={{ backgroundColor: C.orange, borderRadius: R.md, paddingHorizontal: 16, justifyContent: 'center' }}><Ionicons name="add" size={22} color="#1A1205" /></Pressable>
        </Row>
        <Txt v="label" style={{ marginTop: 6 }}>{t('fJoinLeague')}</Txt>
        <Row style={{ gap: 8 }}>
          <TextInput value={code} onChangeText={x => setCode(x.toUpperCase())} placeholder="A1B2C3" autoCapitalize="characters" placeholderTextColor={C.mut} maxLength={6} style={{ flex: 1, color: C.txt, backgroundColor: C.glass, borderRadius: R.md, paddingHorizontal: 12, paddingVertical: 10, letterSpacing: 4 }} />
          <Pressable onPress={() => act({ action: 'join', code })} style={{ backgroundColor: C.blue, borderRadius: R.md, paddingHorizontal: 16, justifyContent: 'center' }}><Ionicons name="enter" size={20} color="#fff" /></Pressable>
        </Row>
        {msg ? <Txt v="sub" c={C.amber}>{msg}</Txt> : null}
      </Card>
      {mine.map(l => (
        <View key={l.code}>
          <Card onPress={() => setOpen(open === l.code ? null : l.code)}>
            <Row style={{ gap: 10 }}><Ionicons name="people" size={20} color={C.amber} /><Txt v="h3" style={{ flex: 1 }}>{l.name}</Txt><Txt v="small">{l.members} · {l.code}</Txt></Row>
          </Card>
          {open === l.code ? <View style={{ marginTop: 8 }}><Ranking league={l.code} /></View> : null}
        </View>
      ))}
    </View>
  );
}

function Rules({ cfg }: { cfg: Config }) {
  const { t, lang } = useApp();
  const fr = lang === 'fr';
  const lines: [string, string][] = [
    [fr ? 'Effectif' : 'Squad', fr ? `8 joueurs : ${cfg.squad.G} meneurs/arrières, ${cfg.squad.F} ailiers, ${cfg.squad.C} pivots · ${cfg.budget} de budget · ${cfg.max_per_club} max par club` : `8 players: ${cfg.squad.G} guards, ${cfg.squad.F} forwards, ${cfg.squad.C} centres · budget ${cfg.budget} · max ${cfg.max_per_club} per club`],
    [fr ? 'Cinq de départ' : 'Starting five', fr ? '5 titulaires avec au moins un meneur/arrière, un ailier et un pivot. Un titulaire qui ne joue pas est remplacé par le premier remplaçant qui a joué.' : '5 starters with at least one guard, one forward and one centre. A starter who does not play is replaced by the first bench player who did.'],
    [t('fCaptain'), fr ? 'Ses points comptent double. S’il ne joue pas, le vice-capitaine prend le brassard.' : 'His points count double. If he does not play, the vice-captain takes the armband.'],
    [t('fTransfers'), fr ? `1 transfert gratuit par journée (2 au plus en réserve), chaque transfert en plus coûte ${cfg.transfer_cost} points.` : `1 free transfer per matchday (bank 2 at most); every extra one costs ${cfg.transfer_cost} points.`],
    [fr ? 'Points' : 'Scoring', fr
      ? `PTS ×1 · REB ×${cfg.scoring.reb} · PD ×${cfg.scoring.ast} · INT ×${cfg.scoring.stl} · CTR ×${cfg.scoring.blk} · 3PTS +${cfg.scoring.p3m} · tir manqué ${cfg.scoring.missed_fg} · lancer manqué ${cfg.scoring.missed_ft} · BP ${cfg.scoring.tov} · faute ${cfg.scoring.pf} · +/- ×${cfg.scoring.pm} · double-double +${cfg.scoring.double_double} · triple-double +${cfg.scoring.triple_double}. Pas de plafond : un joueur efficace marque beaucoup, un joueur qui rate, perd des ballons et fait des fautes pendant de longues minutes peut finir en négatif.`
      : `PTS ×1 · REB ×${cfg.scoring.reb} · AST ×${cfg.scoring.ast} · STL ×${cfg.scoring.stl} · BLK ×${cfg.scoring.blk} · 3PM +${cfg.scoring.p3m} · missed shot ${cfg.scoring.missed_fg} · missed FT ${cfg.scoring.missed_ft} · TO ${cfg.scoring.tov} · foul ${cfg.scoring.pf} · +/- ×${cfg.scoring.pm} · double-double +${cfg.scoring.double_double} · triple-double +${cfg.scoring.triple_double}. No cap: an efficient player scores a lot; one who misses, turns it over and fouls through long minutes can end below zero.`],
    [t('fGrade'), fr ? 'Chaque journée, tes points comparés au meilleur score possible avec ton effectif : A+ (95 %), A (85 %), B (70 %), C (55 %), D.' : 'Each matchday, your points against the best your squad could have scored: A+ (95%), A (85%), B (70%), C (55%), D.'],
  ];
  return (
    <View style={{ gap: 10 }}>
      {lines.map(([h, b]) => <Card key={h}><Txt v="h3" c={C.amber}>{h}</Txt><Txt v="sub" style={{ marginTop: 4 }}>{b}</Txt></Card>)}
      {cfg.chips.map(c => <Card key={c}><Txt v="h3">{t(c)}</Txt><Txt v="sub" style={{ marginTop: 4 }}>{t(`${c}D` as never)}</Txt></Card>)}
    </View>
  );
}
