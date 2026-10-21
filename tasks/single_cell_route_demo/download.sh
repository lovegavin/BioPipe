#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR/input"

URL="https://cf.10xgenomics.com/samples/cell/pbmc3k/pbmc3k_filtered_gene_bc_matrices.tar.gz"
TARBALL="pbmc3k_filtered_gene_bc_matrices.tar.gz"
TARGET="filtered_gene_bc_matrices/hg19/matrix.mtx"

if [ -f "$TARGET" ]; then
  echo "already present, skipping download."
  exit 0
fi

echo "Downloading PBMC 3k from 10x Genomics ..."
curl -fL --max-time 180 -o "$TARBALL" "$URL"

echo "Extracting ..."
tar xzf "$TARBALL"
rm -f "$TARBALL"

if [ ! -f "$TARGET" ]; then
  echo "ERROR: extraction did not produce $TARGET" >&2
  exit 1
fi

ls -la filtered_gene_bc_matrices/hg19/
