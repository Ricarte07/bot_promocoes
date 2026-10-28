import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Bufos Promo | Monitor de preços', description: 'Consulte produtos monitorados e acompanhe os preços disponíveis.' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="pt-BR" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: `(function(){var t;try{t=localStorage.getItem('bufos-theme')}catch(e){}document.documentElement.dataset.theme=t==='dark'||t==='light'?t:window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'})()` }} /></head><body>{children}</body></html>;
}
