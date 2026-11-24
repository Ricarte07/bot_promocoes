import type { Observation } from '../catalog/types';

// Área do desenho, em unidades do viewBox do SVG.
export const CHART = { width: 600, height: 200, padding: 12 };

// O preço muda de uma vez e fica parado até a próxima mudança: o desenho é em
// degraus (anda na horizontal até a data da mudança e então sobe ou desce), não
// uma rampa que sugeriria variação gradual.
export function stepPath(points: Observation[]): string {
  if (points.length < 2) return '';
  const times = points.map((p) => Date.parse(p.date));
  const prices = points.map((p) => p.price);
  const [start, end] = [times[0], times[times.length - 1]];
  const [min, max] = [Math.min(...prices), Math.max(...prices)];
  const { width, height, padding } = CHART;
  const x = (t: number) => ((t - start) / (end - start || 1)) * width;
  // Preço constante fica no meio; senão o maior no topo e o menor embaixo.
  const y = (price: number) =>
    max === min ? height / 2 : padding + (1 - (price - min) / (max - min)) * (height - 2 * padding);
  const round = (n: number) => Math.round(n * 10) / 10;
  let d = `M${round(x(times[0]))} ${round(y(prices[0]))}`;
  for (let i = 1; i < points.length; i++) {
    d += ` H${round(x(times[i]))} V${round(y(prices[i]))}`;
  }
  return d;
}

// Altura da linha do menor preço, na mesma escala do desenho.
export function lowestLineY(points: Observation[]): number {
  const prices = points.map((p) => p.price);
  const [min, max] = [Math.min(...prices), Math.max(...prices)];
  const { height, padding } = CHART;
  return max === min ? height / 2 : height - padding;
}
