import AsyncStorage from '@react-native-async-storage/async-storage';
import { getLocales } from 'expo-localization';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { Key, Lang, translate } from './i18n';

type State = {
  lang: Lang; setLang: (l: Lang) => void; t: (k: Key) => string;
  fav: string | null; setFav: (c: string | null) => void;
  favAsked: boolean; skipFav: () => void;       // the first-launch question "your club?" is asked once, answered or skipped, and never again
  vid: string;                                   // anonymous id of this device (fantasy, votes): no account
  ready: boolean;
};

const Ctx = createContext<State | null>(null);

const newId = () => Array.from({ length: 24 }, () => 'abcdefghijklmnopqrstuvwxyz0123456789'[Math.floor(Math.random() * 36)]).join('');

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (getLocales()[0]?.languageCode === 'en' ? 'en' : 'fr'));
  const [fav, setFavState] = useState<string | null>(null);
  const [vid, setVid] = useState('');
  const [favAsked, setFavAsked] = useState(true);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [[, l], [, f], [, v], [, a]] = await AsyncStorage.multiGet(['lang', 'fav', 'vid', 'favAsked']);
        setFavAsked(!!f || a === '1');
        if (l === 'fr' || l === 'en') setLangState(l);
        if (f) setFavState(f);
        if (v) setVid(v);
        else { const id = newId(); setVid(id); AsyncStorage.setItem('vid', id); }
      } catch { setVid(newId()); }
      setReady(true);
    })();
  }, []);

  const setLang = useCallback((l: Lang) => { setLangState(l); AsyncStorage.setItem('lang', l).catch(() => {}); }, []);
  const setFav = useCallback((c: string | null) => {
    setFavState(c); setFavAsked(true);
    (c ? AsyncStorage.multiSet([['fav', c], ['favAsked', '1']]) : AsyncStorage.removeItem('fav')).catch(() => {});
  }, []);
  const skipFav = useCallback(() => { setFavAsked(true); AsyncStorage.setItem('favAsked', '1').catch(() => {}); }, []);
  const t = useCallback((k: Key) => translate(lang, k), [lang]);
  const value = useMemo(() => ({ lang, setLang, t, fav, setFav, favAsked, skipFav, vid, ready }), [lang, setLang, t, fav, setFav, favAsked, skipFav, vid, ready]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppStateProvider');
  return v;
}
