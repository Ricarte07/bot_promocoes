// Formatação compartilhada; não altera os valores armazenados.
export function formatMoney(value: number): string {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleString('pt-BR', {
    timeZone: 'America/Sao_Paulo',
  });
}

// "15:30": hora em que os dados foram lidos, no horário de Brasília.
export function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString('pt-BR', {
    timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit',
  });
}

// "24/11": eixo do gráfico, no horário de Brasília.
export function formatShortDate(value: string): string {
  return new Date(value).toLocaleDateString('pt-BR', {
    timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit',
  });
}

// "há 12 min", "há 3 h", "há 2 dias". Recebe as horas já calculadas para que
// servidor e navegador mostrem o mesmo texto (a base é a hora da leitura).
export function formatSeenAgo(hours: number): string {
  if (hours < 1) return `há ${Math.max(1, Math.round(hours * 60))} min`;
  if (hours < 48) return `há ${Math.floor(hours)} h`;
  return `há ${Math.floor(hours / 24)} dias`;
}
