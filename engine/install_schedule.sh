#!/usr/bin/env bash
# Install (or remove) the daily JobHunt scan.
#
#   ./engine/install_schedule.sh               install for 6 AM local (launchd on macOS, crontab on Linux)
#   ./engine/install_schedule.sh --hour 7      another hour (0-23, local time)
#   ./engine/install_schedule.sh --print       show what would be installed
#   ./engine/install_schedule.sh --uninstall   remove it
#
# The scan only reads job APIs and writes JobHunt.xlsx. It never applies to anything.
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
LABEL="com.jobhunt.daily"
MARK="# jobhunt-daily"
HOUR=6
ACTION="install"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hour) HOUR="$2"; shift 2 ;;
    --print) ACTION="print"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$HOUR" =~ ^([0-9]|1[0-9]|2[0-3])$ ]] || { echo "--hour must be 0-23" >&2; exit 2; }
chmod +x engine/run_scan.sh
CRON_LINE="0 $HOUR * * * JOBHUNT_EARLIEST_HOUR=$HOUR /bin/bash \"$REPO/engine/run_scan.sh\" $MARK"

case "$(uname -s)" in
  Darwin)
    DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
    case "$ACTION" in
      print) echo "Would install $DEST: daily at $HOUR:00, catching up within 15 min if the Mac was asleep." ;;
      uninstall) launchctl unload "$DEST" 2>/dev/null || true; rm -f "$DEST"; echo "Removed $LABEL." ;;
      install)
        mkdir -p "$HOME/Library/LaunchAgents" data
        sed -e "s|__REPO__|$REPO|g" -e "s|__HOUR__|$HOUR|g" engine/schedule/$LABEL.plist.template > "$DEST"
        launchctl unload "$DEST" 2>/dev/null || true
        launchctl load "$DEST"
        echo "Installed: daily at $HOUR:00. Test it now with: launchctl start $LABEL"
        case "$REPO" in
          "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*)
            echo "WARNING: this folder is privacy-protected on macOS; a background job may be"
            echo "blocked from reading it. Move the project to your home folder (e.g. ~/jobhunt)"
            echo "and run this script again." ;;
        esac ;;
    esac ;;
  Linux)
    case "$ACTION" in
      print) echo "Would add to your crontab:"; echo "  $CRON_LINE" ;;
      uninstall) (crontab -l 2>/dev/null | grep -v "$MARK") | crontab -; echo "Removed the jobhunt line from your crontab." ;;
      install)
        mkdir -p data
        (crontab -l 2>/dev/null | grep -v "$MARK"; echo "$CRON_LINE") | crontab -
        echo "Installed: daily at $HOUR:00 (cron does not catch up on runs missed while the machine was off)." ;;
    esac ;;
  *) echo "Unsupported OS for automatic install. See the README section 'Schedule the scan'." >&2; exit 1 ;;
esac
