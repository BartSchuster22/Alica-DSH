#!/usr/bin/env bash
set -euo pipefail
umask 077
if [[ $# != 1 || -e "$1" || -L "$1" ]]; then printf '%s\n' 'Usage: prepare-stage2.sh NEW_PRIVATE_DIRECTORY (must not exist)' >&2; exit 2; fi
mkdir -m 700 -- "$1"
dir=$(cd -- "$1" && pwd)
asset=dsh-stage2-f390298-linux-amd64.tar.gz
curl --proto '=https' --tlsv1.2 --fail --location --retry 3 --output "$dir/$asset" "https://github.com/BartSchuster22/Alica-DSH/releases/download/dsh-stage2-f390298/$asset"
(cd "$dir"; printf '%s  %s\n' '8fddfc7d2e99f07929955ac10bd6a37de43c9f1504607e80640ca9bf179a49ba' "$asset" | sha256sum --check -)
mkdir -m 700 "$dir/bundle"
tar --extract --gzip --file "$dir/$asset" --strip-components=1 --directory "$dir/bundle"
printf '%s\n' "Verified bundle prepared at $dir/bundle" 'Configure request.json and follow docs/stage2/README.md. No installation has been started.'
