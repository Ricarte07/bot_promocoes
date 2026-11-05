import { readFile } from 'node:fs/promises';
import path from 'node:path';

// Next carrega web/.env.local. A raiz é compartilhada com scraper e notifier.
export async function loadProjectEnv() {
  let contents: string;
  try {
    contents = await readFile(path.resolve(process.cwd(), '../.env'), 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
    throw error;
  }
  for (const line of contents.split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const separator = line.indexOf('=');
    if (separator < 1) continue;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim().replace(/^["']|["']$/g, '');
    if (process.env[key] === undefined) process.env[key] = value;
  }
}
