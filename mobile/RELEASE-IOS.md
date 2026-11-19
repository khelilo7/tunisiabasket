# Putting Tunisia Basket on the App Store — step by step

Built in the cloud by Expo (EAS): you do **not** need Xcode or a Mac build setup. You need a paid Apple developer account and about 1–2 weeks the first time
(Apple's account check, then the app review).

## Before you start
- **The website must be deployed first**: the app reads `https://tunisiabasket.com` and needs this session's server changes (`/api/schedule`, the API's
  cross-origin header). Commit, push, deploy, and check that `https://tunisiabasket.com/api/schedule` answers.
- **The privacy policy page** (Apple requires its address) is in place: `https://tunisiabasket.com/confidentialite` (English: `/en/privacy`), and a **support page or email**.
- The `[TEST]` news only exist on your computer: production shows real news only.

## 1. Apple Developer Program (once, $99 a year)
1. developer.apple.com/programs → *Enroll*, with the Apple ID you want to own the app.
2. **Individual** (your own name shows as the seller; quickest, an ID check) or **Organization** (the club or company name shows; needs a D-U-N-S number,
   free but it takes days). You can move from individual to organization later.
3. Wait for the confirmation email (from a few hours to a few days).

## 2. Create the app in App Store Connect (once)
1. appstoreconnect.apple.com → *Apps* → **+** → *New App*.
2. Platform **iOS**; name **Tunisia Basket** (it must be free on the store; if it is taken, use e.g. *Tunisia Basket – Pro A*);
   primary language **French**; bundle ID **com.tunisiabasket.app** (register it when asked, under *Certificates, IDs & Profiles → Identifiers*); SKU: `tunisiabasket`.
3. Copy the app's **Apple ID** (a number shown on its *App Information* page) into `mobile/eas.json`, in place of `REPLACE_WITH_APP_STORE_CONNECT_APP_ID`.

## 3. Build for iPhone and iPad
```bash
cd mobile
npx eas-cli@latest login            # your Expo account (the same as for Android)
npx eas-cli@latest init             # once, if not done for Android
npx eas-cli@latest build -p ios --profile production
```
- EAS asks to sign in to your **Apple account** and offers to create the **certificate and provisioning profile**: say yes to everything, it stores them.
- 15–25 minutes later the build is ready. The app already declares that it uses no special encryption, so Apple won't ask about it on every build.
- The build number goes up by itself at each build. To change the version users see, edit `"version"` in `app.json` (1.0.0 → 1.0.1).

## 4. Send it to Apple and test it with TestFlight
```bash
npx eas-cli@latest submit -p ios --latest
```
- It uploads the build to App Store Connect (sign in with your Apple ID; EAS can create an *App Store Connect API key* so you are not asked again).
- After 10–30 minutes of Apple's processing, it appears under **TestFlight**.
- *TestFlight → Internal testing* → add yourself and friends (their Apple IDs) → they install **TestFlight** from the App Store and get the app.
  Test it on a real iPhone and an iPad before going further.

## 5. The App Store page
In App Store Connect → your app → the version (1.0):
1. **Screenshots** (required): iPhone 6.9" (1320 × 2868) and iPad 13" (2064 × 2752), 3 to 10 each. Take them on a TestFlight phone and iPad
   (side + volume up), or ask me to make framed ones from the app.
2. **Promotional text, description, keywords** (100 characters: `basket,basketball,tunisie,pro a,ftbb,scores,statistiques,classement,nba,sport`), support URL, marketing URL `https://tunisiabasket.com`.
3. **App icon**: taken from the build (no upload).
4. *App Information*: category **Sports**; content rights: say the app shows third-party content (club names and logos) — see the note below; age rating questionnaire: all "None" → 4+.
5. **App Privacy**: privacy policy URL; *Data collection*: **No, we do not collect data** (true for the store build: no account, no tracking, Fantasy hidden).
6. *Pricing and Availability*: Free; countries: all, or start with Tunisia and France.

## 6. Send for review
1. On the version page: pick the TestFlight build, then fill **App Review Information**: a contact name, phone and email; no sign-in needed; in *Notes*:
   *"Independent statistics app for the Tunisian basketball league (Pro A). All data comes from our website tunisiabasket.com. No account required."*
2. *Version release*: "Manually release" lets you choose the day.
3. **Add for Review** → **Submit**. The review usually takes 1–3 days. If Apple rejects it, the message says why: fix, build, submit again (steps 3–4).

> **Logos and names (guideline 5.2):** Apple can ask whether you may use the clubs' logos and the federation's data. Keep the line "independent, not affiliated
> with the FTBB" (it is in the app's More page), and if asked, answer that the logos identify the clubs whose public results are shown; a written OK from
> the federation or the clubs makes this painless. If they insist, a build with plain club initials instead of logos is a small change.

## 7. Every update after that
```bash
npx eas-cli@latest build -p ios --profile production
npx eas-cli@latest submit -p ios --latest
```
Then in App Store Connect: new version number, pick the build, *What's New* text, submit. New scores, stats and news reach the app by themselves (no update needed).

## Fantasy (hidden)
The store build never shows it. When it launches: add `EXPO_PUBLIC_FANTASY: "1"` to the production `env` in `eas.json`, set `FANTASY=1` on the server, and update
**App Privacy** (a nickname and a device identifier are stored, not linked to the user's identity, not used for tracking).
