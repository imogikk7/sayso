#!/usr/bin/env bash
# Rebuild sayso.pdf from sayso.md with the theme in theme/sayso.css (settings in .marprc.yml).
# Needs Node; Chrome/Chromium is found automatically, or set CHROME_PATH.
set -euo pipefail
cd "$(dirname "$0")"
npx -y @marp-team/marp-cli@4 sayso.md --config-file .marprc.yml --theme-set theme/sayso.css \
  --html --allow-local-files --no-stdin --pdf -o sayso.pdf < /dev/null
