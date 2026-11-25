#!/usr/bin/env bash
# Distribuído sob a licença MIT. Consulte COPYING.
set -euo pipefail

raiz=$(cd "$(dirname "$0")/.." && pwd)
cd "$raiz"
compilacao=${1:-build}
if [[ ! -f "$compilacao/CMakeCache.txt" ]]; then
    echo "Informe um diretório CMake da REAL-26 já configurado." >&2
    exit 2
fi

grep -qx 'REAL26_EXPERIMENTAL_MLDSA65:BOOL=ON' "$compilacao/CMakeCache.txt" ||
    { echo "A compilação deve incluir ML-DSA-65." >&2; exit 2; }
grep -qx 'REAL26_BENCH_15M:BOOL=OFF' "$compilacao/CMakeCache.txt" ||
    { echo "A candidata exige o limite normal de 4 milhões." >&2; exit 2; }

cmake --build "$compilacao" --target bitcoind bitcoin-cli real26_mldsa65_sign_test -j "${REAL26_JOBS:-5}"
resultado=$(mktemp "$compilacao/real26-candidata.XXXXXXXX")
trap 'rm -f -- "$resultado"' EXIT
python3 "$compilacao/test/functional/test_runner.py" \
    feature_real26_regtest.py feature_real26_refs.py feature_real26_testnet.py \
    feature_real26_asert.py feature_real26_asert_pq.py \
    --jobs=4 --usecli --resultsfile="$resultado"

python3 - "$resultado" <<'PY'
import csv
import sys
from pathlib import Path

esperados = {
    "feature_real26_regtest.py",
    "feature_real26_refs.py",
    "feature_real26_asert.py",
    "feature_real26_asert_pq.py",
    "feature_real26_asert_pq.py --compartilhado",
    "feature_real26_testnet.py",
    "feature_real26_testnet.py --refs",
    "feature_real26_testnet.py --ensaio",
}
with Path(sys.argv[1]).open(newline="", encoding="utf-8") as arquivo:
    linhas = [linha for linha in csv.DictReader(arquivo) if linha["test"] != "ALL"]
if len(linhas) != len(esperados) or {linha["test"] for linha in linhas} != esperados or any(
    linha["status"] != "Passed" for linha in linhas
):
    raise SystemExit("A verificação exige aprovação em todas as suítes selecionadas.")
PY
mv -- "$resultado" "$compilacao/real26-candidata.csv"
