import Image from 'next/image';

export default function Brand({ tagline = false }: { tagline?: boolean }) {
  return <span className="brand-lockup">
    <span className="brand-symbol" aria-hidden="true">
      <Image src="/bufos-logo.jpg" alt="" width={160} height={200} className="brand-image" />
    </span>
    <span className="brand-wordmark">bufos <span>promo</span>{tagline && <small>MONITOR DE PREÇOS</small>}</span>
  </span>;
}
