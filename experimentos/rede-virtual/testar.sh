#!/usr/bin/env bash
# Distribuído sob a licença MIT. Consulte COPYING.
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 || ( $# == 3 && "$3" != carga && "$3" != frio && "$3" != misto && "$3" != misto80 && "$3" != refs ) ]]; then
    echo "Uso: bash $0 IMAGEM_QCOW2 DIRETORIO_DOS_BINARIOS [carga|frio|misto|misto80|refs]" >&2
    exit 2
fi
imagem=$(realpath -- "$1")
binarios=$(realpath -- "$2")
modo=${3:-local}
codigo=$(cd "$(dirname "$0")" && pwd)
execucao=$(mktemp -d /opt/real26-vms/teste.XXXXXXXX)
echo "Arquivos do teste: $execucao"
cd "$execucao"
mkdir -p payload/lib
cp "$binarios"/{bitcoind,bitcoin-cli} "$codigo/convidado.py" payload/
if [[ "$modo" != local ]]; then
    cp "$binarios/real26_mldsa65_sign_test" "$codigo/carga.py" "$codigo/frio.py" payload/
    cp -r "$codigo/../../test/functional/test_framework" payload/
fi
for binario in payload/bitcoind payload/bitcoin-cli payload/real26_mldsa65_sign_test; do
    [[ -f "$binario" ]] || continue
    while read -r biblioteca; do
        cp -L "$biblioteca" payload/lib/
    done < <(ldd "$binario" | awk '/libstdc\+\+|libgcc_s|libsqlite3|libcrypto/ && $3 ~ /^\// {print $3}')
done
if [[ "$modo" == misto || "$modo" == misto80 ]]; then cp "$codigo/misto.py" payload/; fi
if [[ "$modo" == refs ]]; then
    cp "$codigo/refs.py" payload/
fi
genisoimage -quiet -R -V REAL26 -o payload.iso payload

preparar_no() {
    local numero=$1
    qemu-img create -q -f qcow2 -F qcow2 -b "$imagem" "no-$numero.qcow2"
    qemu-img resize -q "no-$numero.qcow2" 5G
    cat > "rede-$numero.yml" <<EOF
version: 2
ethernets:
  real26:
    match:
      macaddress: "52:54:00:26:00:0$numero"
    dhcp4: false
    dhcp6: false
    addresses: [192.168.76.$numero/24]
EOF
    cat > "no-$numero.yml" <<EOF
#cloud-config
hostname: real26-vm-$numero
ssh_pwauth: false
disable_root: true
package_update: false
runcmd:
  - [mkdir, -p, /mnt/real26]
  - [mount, -L, REAL26, /mnt/real26]
  - [systemd-run, --unit=real26-medicao, --property=RemainAfterExit=yes, /bin/sh, -c, 'LD_LIBRARY_PATH=/mnt/real26/lib python3 -u /mnt/real26/convidado.py $numero $modo > /dev/ttyS1 2>&1']
EOF
    printf 'instance-id: real26-vm-%s\n' "$numero" > "meta-$numero"
    cloud-localds --network-config="rede-$numero.yml" "seed-$numero.iso" "no-$numero.yml" "meta-$numero"
}
preparar_no 1
preparar_no 2

aceleracao=${REAL26_ACELERACAO:-kvm}
cpu=host
if [[ "$aceleracao" == tcg ]]; then cpu=max; fi
processos=()
encerrar() {
    for processo in "${processos[@]}"; do
        kill "$processo" 2>/dev/null || true
    done
    for processo in "${processos[@]}"; do
        wait "$processo" 2>/dev/null || true
    done
}
trap encerrar EXIT
trap "exit 130" INT TERM
iniciar_no() {
    local numero=$1 canal=$2 porta=$3
    qemu-system-x86_64 -accel "$aceleracao" -cpu "$cpu" -m 1400 -smp 2 \
        -display none -monitor none -serial "file:no-$numero.serial" -serial "file:no-$numero.teste" \
        -drive "file=no-$numero.qcow2,if=virtio" \
        -drive "file=seed-$numero.iso,media=cdrom,readonly=on" \
        -drive "file=payload.iso,media=cdrom,readonly=on" \
        -netdev "socket,id=rede,$canal=127.0.0.1:$porta" \
        -device "virtio-net-pci,netdev=rede,mac=52:54:00:26:00:0$numero" \
        >"no-$numero.qemu.log" 2>&1 &
    processos+=("$!")
}
porta_base=${REAL26_PORTA:-29796}
iniciar_no 1 listen "$porta_base"
porta_par=$porta_base
if [[ "$modo" != local ]]; then
    porta_par=$((porta_base + 1))
    python3 "$codigo/enlace.py" "$porta_base" "$porta_par" > enlace.log 2>&1 &
    processos+=("$!")
fi
sleep 1
iniciar_no 2 connect "$porta_par"

coord=2
if [[ "$modo" == frio || "$modo" == misto || "$modo" == misto80 || "$modo" == refs ]]; then coord=1; fi
for ((tentativa=0; tentativa<800; tentativa++)); do
    if grep -q '^REAL26_RESULTADO:' "no-$coord.teste" 2>/dev/null; then
        grep '^REAL26_RESULTADO:' "no-$coord.teste"
        exit 0
    fi
    if grep -q '^REAL26_FALHA:' no-{1,2}.teste 2>/dev/null; then break; fi
    if ! kill -0 "${processos[@]}" 2>/dev/null; then break; fi
    sleep 1
done
tail -n 22 no-{1,2}.{qemu.log,teste} >&2 || true
if [[ -f enlace.log ]]; then tail -n 12 enlace.log >&2; fi
echo "Teste interrompido. Consulte os logs em $execucao." >&2
exit 1
