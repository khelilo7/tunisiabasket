# Tunisia Basket — mobile app (Android first, then iOS; phones and tablets)

A native React Native app (Expo, Expo Router), not a wrapper of the website: its own screens, navigation and look, the website's public API as data
(`/api/home`, `/api/schedule`, `/api/games/<id>`, `/api/players`, `/api/teams/<code>`, `/api/overview`, `/api/history`, `/api/records`...). The admin stays on the website.

**Screens.** Home (my club, next matchday, MVP, latest results, leaders, table) · Scores (matchday strip, results and fixtures; a game: scoreboard, MVP, records it set, top
performers, box score, team comparison) · Standings (Pro A / National One) · Players (leaders by stat, search; a player: hero, season averages, shooting, game log) · team
pages (form, next game, roster, results; ⭐ makes it *my club*) · History (champions since 1955-56, each season's format, tables and series) · Records · More (club, language).
French by default, English on an English phone; the last answers are kept on the phone, so the app opens offline. Two columns from 768 px wide (tablets), three from 1100.

**Fantasy (hidden).** A Fantasy Pro A tab appears only when the app is built with `EXPO_PUBLIC_FANTASY=1` *and* the server runs with `FANTASY=1` (see `../fantasy.py`):
8 players, budget, captain, chips, transfers, a grade per matchday, a ranking and private leagues, no account (the device's random id). Store builds leave it out.

## Run it on your computer
```bash
npm install
cp .env.local.example .env.local      # EXPO_PUBLIC_API_URL=http://localhost:5055, EXPO_PUBLIC_FANTASY=1
npx expo start                         # a = Android emulator, i = iOS simulator, w = web preview; Expo Go on a phone (same Wi-Fi)
```
The website runs beside it: `FANTASY=1 FANTASY_TEST=1 python app.py` (port 5055). On an Android emulator `localhost` is reached as `10.0.2.2` (done for you).
`FANTASY_TEST=1` lets the app save a squad for a matchday already played, to try the game on real results.

## Build for the stores (EAS, no Android Studio needed)
Step by step, accounts and store consoles included: **[RELEASE-ANDROID.md](RELEASE-ANDROID.md)** (Google Play) and **[RELEASE-IOS.md](RELEASE-IOS.md)** (App Store); store images in `store/`.

```bash
npx eas-cli@latest login
npx eas-cli@latest build -p android --profile preview      # an .apk to install on phones for testing
npx eas-cli@latest build -p android --profile production   # the .aab for Google Play
npx eas-cli@latest build -p ios --profile production       # later, for the App Store (Apple developer account)
```
Both profiles point at `https://tunisiabasket.com` and do not set `EXPO_PUBLIC_FANTASY`, so the fantasy tab stays hidden.

Checks: `npx tsc --noEmit` and `npx expo lint`.
