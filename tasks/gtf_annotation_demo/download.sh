#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR/input"

BASE="https://ftp.ensembl.org/pub/release-110"

if [ ! -s saccharomyces_cerevisiae.gtf.gz ]; then
  curl -fL -o saccharomyces_cerevisiae.gtf.gz \
    "$BASE/gtf/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.110.gtf.gz"
fi

if [ ! -s saccharomyces_cerevisiae.gff3.gz ]; then
  curl -fL -o saccharomyces_cerevisiae.gff3.gz \
    "$BASE/gff3/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.110.gff3.gz"
fi

ls -lh
