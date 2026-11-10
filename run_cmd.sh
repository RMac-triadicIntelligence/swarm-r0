#!/usr/bin/env bash
# run_cmd.sh LABEL CMD... : runs CMD; appends the exact command, start/end time (America/Chicago) and exit code to outputs/COMMANDS.log
label="$1"; shift
start="$(date '+%Y-%m-%d %H:%M:%S %Z')"
"$@"
rc=$?
end="$(date '+%Y-%m-%d %H:%M:%S %Z')"
printf '[%s] start=%s end=%s exit=%d cwd=%s\n  $ %s\n' "$label" "$start" "$end" "$rc" "$PWD" "$*" >> outputs/COMMANDS.log
exit $rc
