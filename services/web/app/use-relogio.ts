'use client';

import { useSyncExternalStore } from 'react';

// Relógio da página: anda de 30 em 30 segundos enquanto ela está aberta, para o
// "visto há X" e o corte de 24 h das promoções não congelarem na hora em que a
// página abriu. Antes de a página ganhar vida no navegador, vale a hora em que o
// servidor leu os dados, para o texto sair igual no servidor e no navegador.
const PASSO = 30_000;

function assinar(avisar: () => void) {
  const id = setInterval(avisar, PASSO);
  return () => clearInterval(id);
}

// Arredondado ao passo: o valor só muda a cada 30 s, então a tela não redesenha à toa.
function agora() {
  return Math.floor(Date.now() / PASSO) * PASSO;
}

export function useRelogio(lidoEm: number): number {
  return useSyncExternalStore(assinar, agora, () => lidoEm);
}
