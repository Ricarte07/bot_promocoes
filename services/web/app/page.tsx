import { Suspense } from 'react';
import { connection } from 'next/server';
import { getCatalog } from '../lib/catalog';
import Brand from './brand';
import Dashboard from './dashboard';

async function Catalog() {
  await connection();
  return <Dashboard catalog={await getCatalog()} />;
}
export default function Home() {
  return (
    <Suspense
      fallback={
        <main className="loading" role="status">
          <span className="brand">
            <Brand />
          </span>
          <h1>Buscando seus produtos…</h1>
          <p>Consultando a fonte de dados disponível.</p>
        </main>
      }
    >
      <Catalog />
    </Suspense>
  );
}
