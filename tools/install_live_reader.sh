#!/bin/bash
# Installs the live score reader on a Mac, once:  bash tools/install_live_reader.sh [TOKEN] [SERVER]
#
#   ~/TunisiaBasketLive/                       the reader (live_reader.py, winlist), its own Python, its settings (config) and its log (reader.log)
#   /Applications/Tunisia Basket Live.app      double-click: starts reading every browser window titled "Diwan Sport" (one window per game);
#                                              double-click again while it runs: what it follows, Stop, or the log
#
# The token comes from the server: sudo proastats-admin new-livescore-token. Without one, the installer asks for it.
# Needs Homebrew's tesseract (brew install tesseract) and Apple's command line tools (xcode-select --install) for swiftc.
# The reader runs in a Terminal window, so Terminal needs the Screen Recording permission (System Settings > Privacy & Security > Screen & System Audio
# Recording): switch it on, quit Terminal, then double-click the app again. (An app made with osacompile has no stable identity, so macOS does not keep the
# permission for it.)
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/TunisiaBasketLive"
APP="/Applications/Tunisia Basket Live.app"
TOKEN="${1:-}"
SERVER="${2:-https://tunisiabasket.com}"

command -v tesseract >/dev/null || { echo "tesseract is missing: brew install tesseract, then run this again."; exit 1; }
command -v swiftc >/dev/null || { echo "swiftc is missing: xcode-select --install, then run this again."; exit 1; }
if [ -z "$TOKEN" ] && [ -f "$DEST/config" ]; then TOKEN="$(sed -n 's/^TOKEN=//p' "$DEST/config")"; fi
if [ -z "$TOKEN" ]; then read -r -p "Live-score token (sudo proastats-admin new-livescore-token on the server): " TOKEN; fi

mkdir -p "$DEST"
cp "$SRC/live_reader.py" "$SRC/winlist.swift" "$DEST/"
echo "==> Python packages"
[ -x "$DEST/venv/bin/python" ] || python3 -m venv "$DEST/venv"
"$DEST/venv/bin/pip" install -q --upgrade pip numpy pillow scipy
echo "==> Window lister"
swiftc -O "$DEST/winlist.swift" -o "$DEST/winlist"
umask 077
printf 'SERVER=%s\nTOKEN=%s\n' "$SERVER" "$TOKEN" > "$DEST/config"

cat > "$DEST/run.sh" <<'RUN'
#!/bin/bash
# Started by "Tunisia Basket Live.app" in a Terminal window (Terminal has the Screen Recording permission; an app made with osacompile cannot keep it).
# Keeps the Mac and its screen awake while it reads (a sleeping screen stops drawing the video). Close the window, or the app's Stop, to stop.
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
SERVER="$(sed -n 's/^SERVER=//p' config)"; TOKEN="$(sed -n 's/^TOKEN=//p' config)"
printf '\033]0;Tunisia Basket Live\007'
echo "Tunisia Basket Live: reading every window titled \"Diwan Sport\" (one window per game, behind other windows is fine, not minimised)."
echo "Scores go to $SERVER. Close this window to stop."
: > reader.log
export LIVESCORE_TOKEN="$TOKEN"                     # the token stays out of the process list (ps), unlike a --token argument
caffeinate -di ./venv/bin/python -u live_reader.py --server "$SERVER" --winlist ./winlist 2>&1 | tee -a reader.log
RUN
chmod 755 "$DEST/run.sh"

echo "==> The app"
TMP="$(mktemp -d)"
cat > "$TMP/app.applescript" <<'OSA'
on run
	set base to (POSIX path of (path to home folder)) & "TunisiaBasketLive/"
	set isRunning to do shell script "pgrep -f '[l]ive_reader.py --server' >/dev/null && echo yes || echo no"
	if isRunning is "yes" then
		set statusLines to do shell script "grep -E 'following|->|refused|minimised|has not changed|no scoreboard' " & quoted form of (base & "reader.log") & " | tail -4 || true"
		set r to button returned of (display dialog "The live score reader is running." & return & return & statusLines buttons {"Stop", "Open the log", "Keep running"} default button "Keep running" with title "Tunisia Basket Live")
		if r is "Stop" then
			do shell script "pkill -f '[l]ive_reader.py --server' || true"
			display notification "Stopped: nothing is sent any more." with title "Tunisia Basket Live"
		else if r is "Open the log" then
			do shell script "open -e " & quoted form of (base & "reader.log")
		end if
	else
		tell application "Terminal"
			do script quoted form of (base & "run.sh")
		end tell
		delay 6
		set firstLines to do shell script "tail -3 " & quoted form of (base & "reader.log") & " || true"
		if firstLines contains "refused" then
			display dialog "macOS does not let Terminal read the screen yet." & return & return & "System Settings > Privacy & Security > Screen & System Audio Recording: switch on Terminal, quit Terminal, then double-click this app again." buttons {"Open the settings", "OK"} default button "Open the settings" with title "Tunisia Basket Live"
			if button returned of result is "Open the settings" then do shell script "open 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'"
		else
			display notification "Reading every window titled Diwan Sport. The Terminal window shows each score sent." with title "Tunisia Basket Live"
		end if
	end if
end run
OSA
rm -rf "$APP"
osacompile -o "$APP" "$TMP/app.applescript"
rm -rf "$TMP"
echo
echo "Done. Open Tunisia Basket Live in Applications, or: open \"$APP\""
echo "Server: $SERVER   Log: $DEST/reader.log"
