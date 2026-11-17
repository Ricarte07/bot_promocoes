// Formatação compartilhada; não altera os valores armazenados.
export function formatMoney(value: number): string {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleString('pt-BR', {
    timeZone: 'America/Fortaleza',
  });
}
