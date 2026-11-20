import AsyncStorage from '@react-native-async-storage/async-storage';
import { getLocales } from 'expo-localization';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { Key, Lang, translate } from './i18n';
import { DEFAULT_PREFS, NotifPrefs } from './push';

type State = {
  lang: Lang; setLang: (l: Lang) => void; t: (k: Key) => string;
  fav: string | null; setFav: (c: string | null) => void;
  favPrompt: boolean; askFav: () => void; skipFav: (never?: boolean) => void;   // "your club?": asked at first launch, again 3 days after a "later", never after "don't ask"; askFav opens it any time
  notif: NotifPrefs; setNotif: (p: NotifPrefs) => void;                          // what this phone wants to be told (push.ts)
  vid: string;                                   // anonymous id of this device (fantasy, votes, predictions): no account
  ready: boolean;
};

const Ctx = createContext<State | null>(null);

// 32 hex characters: the form the server's votes and predictions accept
const newId = () => Array.from({ length: 32 }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('');
const VALID = /^[a-f0-9]{16,64}$/;

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (getLocales()[0]?.languageCode === 'en' ? 'en' : 'fr'));
  const [fav, setFavState] = useState<string | null>(null);
  const [notif, setNotifState] = useState<NotifPrefs>(DEFAULT_PREFS);
  const [vid, setVid] = useState('');
  const [favPrompt, setFavPrompt] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [[, l], [, f], [, v], [, later], [, never], [, n]] = await AsyncStorage.multiGet(['lang', 'fav', 'vid', 'favLater', 'favNever', 'notif']);
        setFavPrompt(!f && never !== '1' && (!later || Date.now() - Number(later) > 3 * 864e5));
        if (l === 'fr' || l === 'en') setLangState(l);
        if (f) setFavState(f);
        if (n) setNotifState({ ...DEFAULT_PREFS, ...JSON.parse(n) });
        if (v && VALID.test(v)) setVid(v);
        else { const id = newId(); setVid(id); AsyncStorage.setItem('vid', id); }
      } catch { setVid(newId()); }
      setReady(true);
    })();
  }, []);

  const setLang = useCallback((l: Lang) => { setLangState(l); AsyncStorage.setItem('lang', l).catch(() => {}); }, []);
  const setFav = useCallback((c: string | null) => {
    setFavState(c); setFavPrompt(false);
    (c ? AsyncStorage.setItem('fav', c) : AsyncStorage.removeItem('fav')).catch(() => {});
  }, []);
  const setNotif = useCallback((p: NotifPrefs) => { setNotifState(p); AsyncStorage.setItem('notif', JSON.stringify(p)).catch(() => {}); }, []);
  const askFav = useCallback(() => setFavPrompt(true), []);
  const skipFav = useCallback((never?: boolean) => {
    setFavPrompt(false);
    AsyncStorage.setItem(never ? 'favNever' : 'favLater', never ? '1' : String(Date.now())).catch(() => {});
  }, []);
  const t = useCallback((k: Key) => translate(lang, k), [lang]);
  const value = useMemo(() => ({ lang, setLang, t, fav, setFav, favPrompt, askFav, skipFav, notif, setNotif, vid, ready }),
    [lang, setLang, t, fav, setFav, favPrompt, askFav, skipFav, notif, setNotif, vid, ready]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppStateProvider');
  return v;
}
