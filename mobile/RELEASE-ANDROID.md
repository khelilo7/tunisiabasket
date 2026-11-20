# Putting Tunisia Basket on Android — step by step

Everything is built in the cloud by Expo (EAS): no Android Studio, no Java on your Mac. iPhone comes later the same way (`-p ios`, with an Apple developer account).

## 0. Try it first (today, free)
1. On your Mac: in `basketstats/`, run `FANTASY=1 FANTASY_TEST=1 python app.py` (the API, port 5055).
2. In `basketstats/mobile/`: `npm install` once, then `npx expo start`.
3. On an Android phone on the **same Wi-Fi**: install **Expo Go** from the Play Store, open it and scan the QR code the terminal shows.
   The phone then talks to your Mac. (Or press `a` to open the Android emulator on the Mac.)

## 1. Accounts (once)
1. **Expo account** (free): sign up at expo.dev. Then, in `mobile/`: `npx eas-cli@latest login`.
2. **Google Play developer account**: play.google.com/console — a one-time fee of $25, an ID check (it can take a few days). Use the club/brand's Google account, not a personal one if possible.

## 2. Link the project to Expo (once)
```bash
cd mobile
npx eas-cli@latest init        # creates the project on expo.dev and writes its id into app.json
```
The app's identity is already set in `app.json`: name *Tunisia Basket*, Android package `com.tunisiabasket.app` (it can never change after the first upload: change it now if you want another).

## 2b. Notifications on Android (once, free — before the build that should send them)
Expo Go cannot receive notifications; an installed build can, once Google's push service (Firebase) knows the app:
1. console.firebase.google.com → *Add project* (e.g. "Tunisia Basket", Analytics off) → *Add app* → Android, package `com.tunisiabasket.app` →
   download **google-services.json** into `mobile/` and add to `app.json`, under `"android"`: `"googleServicesFile": "./google-services.json"`.
2. Firebase → ⚙ *Project settings* → *Service accounts* → *Generate new private key* (a JSON file; keep it private, never commit it).
3. `npx eas-cli@latest credentials` → Android → production → *Google Service Account Key for Push Notifications (FCM V1)* → upload that JSON.
4. Build again (step 3). In the app: More → Notifications → "My club" (or pick a club: the picker offers it). The server sends a notification when a result,
   a news item or a vote is published (it checks every minute; the first run after a deployment only records what already exists).

## 3. A test build to install on phones (APK)
```bash
npx eas-cli@latest build -p android --profile preview
```
- EAS asks to generate an Android **keystore**: say yes, it keeps it for you (never lose it: it signs every update).
- After about 10–15 minutes you get a link and a QR code: open it on an Android phone, download, install (allow "install unknown apps").
- This build uses the real site `https://tunisiabasket.com` and has **no Fantasy tab**.
  The production server must run the new code first (the app needs `/api/schedule` and the API's cross-origin header): commit, push, deploy as usual.

## 4. The store build (AAB)
```bash
npx eas-cli@latest build -p android --profile production
```
The version code goes up by itself at every build (`autoIncrement`). To change the version users see, edit `"version"` in `app.json` (1.0.0 → 1.0.1).

## 5. Create the app in Google Play Console (once)
1. *Create app*: name **Tunisia Basket**, default language **French**, App, Free.
2. **Store listing**: short description (80 chars) and full description (FR, add EN as a translation); app icon `store/icon-512.png`;
   feature graphic `store/feature-graphic-1024x500.png`; at least 2 phone screenshots (take them in the app: power + volume down), 7" and 10" tablet screenshots if you want the tablet badge.
3. **Privacy policy URL** (required): a page on the site, e.g. `https://tunisiabasket.com/confidentialite` (English: `/en/privacy`); it is in place (`privacy.py`).
4. **App content** forms: ads = No; target audience = 13+ (or 18+ to keep it simple); content rating questionnaire (sports, no violence → "Everyone");
   **Data safety**: no data collected or shared (true while Fantasy is hidden — revisit when it launches); news app = No; government app = No.
5. Category: **Sports**. Contact email: the brand's.

## 6. First release: internal testing, then production
1. Play Console → *Testing → Internal testing* → create a release → upload the `.aab` from step 4 (download it from the EAS link), or automatically:
   `npx eas-cli@latest submit -p android --latest` (needs a Google service-account JSON key the first time: Play Console → Setup → API access; EAS explains each click).
2. Add testers (emails), share the opt-in link, test on a few phones.
3. *Production* → promote the release → *Send for review*. Google's first review usually takes a few days; updates are faster.

## 7. Every update after that
- Change the code, then `npx eas-cli@latest build -p android --profile production` and `npx eas-cli@latest submit -p android --latest`, then promote in the Play Console.
- The data (scores, stats, records) updates by itself from the website: no new app version is needed for new games.

## iPhone and iPad
Step by step in **[RELEASE-IOS.md](RELEASE-IOS.md)**: same code, same commands with `-p ios`.

## Fantasy (hidden)
Store builds never show it. To try it: `.env.local` with `EXPO_PUBLIC_FANTASY=1` and the server with `FANTASY=1` (`FANTASY_TEST=1` to play past matchdays).
When it launches: add `EXPO_PUBLIC_FANTASY: "1"` to the production profile's `env` in `eas.json`, set `FANTASY=1` on the server, update the Data safety form (a nickname and a device id are stored).
