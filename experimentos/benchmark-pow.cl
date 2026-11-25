// Distribuído sob a licença MIT. Consulte COPYING.
__constant uint K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
__constant uint IV[8] = {
    0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
};

uint direita(uint palavra, uint bits) { return (palavra >> bits) | (palavra << (32U - bits)); }

void transformar(uint estado[8], uint w[16])
{
    uint a = estado[0], b = estado[1], c = estado[2], d = estado[3];
    uint e = estado[4], f = estado[5], g = estado[6], h = estado[7];
    #pragma unroll
    for (uint i = 0; i < 64; ++i) {
        uint j = i & 15;
        if (i >= 16) {
            uint x = w[(i + 1) & 15];
            uint y = w[(i + 14) & 15];
            w[j] += (direita(x, 7) ^ direita(x, 18) ^ (x >> 3))
                + w[(i + 9) & 15] + (direita(y, 17) ^ direita(y, 19) ^ (y >> 10));
        }
        uint t1 = h + (direita(e, 6) ^ direita(e, 11) ^ direita(e, 25))
            + ((e & f) ^ (~e & g)) + K[i] + w[j];
        uint t2 = (direita(a, 2) ^ direita(a, 13) ^ direita(a, 22))
            + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    estado[0] += a; estado[1] += b; estado[2] += c; estado[3] += d;
    estado[4] += e; estado[5] += f; estado[6] += g; estado[7] += h;
}

uint duplo_sha256(__global const uint *cabecalho, uint nonce, uint palavra)
{
    uint estado[8], w[16];
    for (uint i = 0; i < 8; ++i) estado[i] = IV[i];
    for (uint i = 0; i < 16; ++i) w[i] = cabecalho[i];
    transformar(estado, w);

    for (uint i = 0; i < 3; ++i) w[i] = cabecalho[16 + i];
    w[3] = (nonce << 24) | ((nonce & 0xff00U) << 8) | ((nonce >> 8) & 0xff00U) | (nonce >> 24);
    for (uint i = 4; i < 16; ++i) w[i] = 0;
    w[4] = 0x80000000U;
    w[15] = 640;
    transformar(estado, w);

    for (uint i = 0; i < 8; ++i) w[i] = estado[i];
    for (uint i = 8; i < 16; ++i) w[i] = 0;
    w[8] = 0x80000000U;
    w[15] = 256;
    for (uint i = 0; i < 8; ++i) estado[i] = IV[i];
    transformar(estado, w);
    return estado[palavra];
}

__kernel void medir(__global const uint *cabecalho, uint inicio, __global uint *saida)
{
    const uint id = get_global_id(0);
    saida[id] = duplo_sha256(cabecalho, inicio + id, 0);
}

__kernel void procurar(__global const uint *cabecalho, uint inicio, volatile __global uint *candidato, uint prefixo_alvo)
{
    const uint id = get_global_id(0);
    const uint word = duplo_sha256(cabecalho, inicio + id, 7);
    const uint prefixo = (word << 24) | ((word & 0xff00U) << 8) | ((word >> 8) & 0xff00U) | (word >> 24);
    if (prefixo <= prefixo_alvo) atomic_min(candidato, id);
}
