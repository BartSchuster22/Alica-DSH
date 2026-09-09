#!/usr/bin/env bash
set -euo pipefail
umask 077
if [[ $# != 1 || -e "$1" || -L "$1" ]]; then printf '%s\n' 'Usage: prepare-stage2.sh NEW_PRIVATE_DIRECTORY (must not exist)' >&2; exit 2; fi
mkdir -m 700 -- "$1"
dir=$(cd -- "$1" && pwd)
asset=dsh-stage2-72a4812-linux-amd64.tar.gz
curl --proto '=https' --tlsv1.2 --fail --location --retry 3 --output "$dir/$asset" "https://github.com/BartSchuster22/Alica-DSH/releases/download/dsh-stage2-72a4812/$asset"
(cd "$dir"; printf '%s  %s\n' 'e4935f81096561ec41050250e20f6d0a62dd7e3cd3d9bf4b37607860752964fb' "$asset" | sha256sum --check -)
mkdir -m 700 "$dir/bundle"
tar --extract --gzip --file "$dir/$asset" --strip-components=1 --directory "$dir/bundle"
printf '%s\n' "Verified bundle prepared at $dir/bundle" 'Configure request.json and follow docs/stage2/README.md. No installation has been started.'
