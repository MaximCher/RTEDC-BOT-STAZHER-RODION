/* eslint-disable @typescript-eslint/no-var-requires */
import 'dotenv/config';
import OpenAI from 'openai';
import { promises as fs } from 'fs';
import path from 'path';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

const openai = new OpenAI({ apiKey: OPENAI_API_KEY! });

type ManualDocConfig = {
  id: string;
  file: string;
  title: string;
  docType: string;
};

const MANUAL_DOCS: ManualDocConfig[] = [
  {
    id: 'strategy-2028',
    file: 'content/manual/strategy-2028.md',
    title: 'Стратегия развития цифровой платформы СРВТ.РФ 2025–2028',
    docType: 'strategy'
  },
  {
    id: 'block-1-payments',
    file: 'content/manual/block-1-payments.md',
    title: 'Блок 1. Международные платежи и транзакции',
    docType: 'payments'
  },
  {
    id: 'block-2-finance-subsidies',
    file: 'content/manual/block-2-finance-subsidies.md',
    title: 'Блок 2. Финансирование, рефинансирование и субсидии',
    docType: 'finance'
  },
  {
    id: 'block-3-logistics',
    file: 'content/manual/block-3-logistics.md',
    title: 'Блок 3. Логистика и импорт под ключ',
    docType: 'logistics'
  },
  {
    id: 'block-4-marketing',
    file: 'content/manual/block-4-marketing.md',
    title: 'Блок 4. Маркетинг портала СРВТ.РФ и доп продукты',
    docType: 'marketing'
  },
  {
    id: 'block-5-events-gr',
    file: 'content/manual/block-5-events-gr.md',
    title: 'Блок 5. События ВЭД России и GR-коммуникации',
    docType: 'events-gr'
  },
  {
    id: 'academy',
    file: 'content/manual/academy.md',
    title: 'Академия экспорта и импорта СРВТ',
    docType: 'academy'
  },
  {
    id: 'club',
    file: 'content/manual/club.md',
    title: 'Клуб экспортёров и импортёров СРВТ',
    docType: 'club'
  },
  {
    id: 'cold-call-script',
    file: 'content/manual/cold-call-script.md',
    title: 'Скрипт холодного обзвона СРВТ',
    docType: 'script'
  }
];

type DocumentRow = {
  source: string;
  url: string;
  content: string;
  chunk_index: number;
  embedding: number[];
};

function chunkText(text: string, maxLen = 800, overlap = 150): string[] {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (!clean.length) {
    return [];
  }

  const chunks: string[] = [];
  let start = 0;

  while (start < clean.length) {
    const end = Math.min(start + maxLen, clean.length);
    chunks.push(clean.slice(start, end));
    if (end === clean.length) break;
    start = end - overlap;
  }

  return chunks;
}

async function embedBatch(texts: string[]): Promise<number[][]> {
  if (!texts.length) return [];

  const res = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: texts
  });

  return res.data.map((item) => item.embedding);
}

async function insertDocuments(rows: DocumentRow[]): Promise<void> {
  const endpoint = `${SUPABASE_URL}/rest/v1/documents`;

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_SERVICE_ROLE_KEY!,
      Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY!}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation'
    },
    body: JSON.stringify(rows)
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    console.error('Supabase insert error:', response.status, response.statusText, text);
    throw new Error(`Failed to insert documents, status ${response.status}`);
  }
}

async function clearInternalDocuments() {
  const endpoint = `${SUPABASE_URL}/rest/v1/documents?source=eq.srvt.internal`;

  const response = await fetch(endpoint, {
    method: 'DELETE',
    headers: {
      apikey: SUPABASE_SERVICE_ROLE_KEY!,
      Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY!}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation'
    }
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    console.error('Supabase delete error:', response.status, response.statusText, text);
    throw new Error(`Failed to clear internal documents, status ${response.status}`);
  }
}

async function ingestManualDoc(doc: ManualDocConfig) {
  const filePath = path.resolve(doc.file);
  console.log(`>>> Ингест: ${doc.id} (${filePath})`);

  const raw = await fs.readFile(filePath, 'utf8');
  const text = raw.replace(/\s+/g, ' ').trim();
  if (!text) {
    console.warn(`Пустой текст в ${doc.file}, пропускаю`);
    return;
  }

  const chunks = chunkText(text, 800, 150);
  console.log(`Документ ${doc.id} порезан на ${chunks.length} чанков`);

  const embeddings = await embedBatch(chunks);

  const rows: DocumentRow[] = chunks.map((content, idx) => ({
    source: 'srvt.internal',
    url: `internal:${doc.id}`,
    content,
    chunk_index: idx,
    embedding: embeddings[idx]
  }));

  await insertDocuments(rows);
  console.log(`✅ Вставлено ${rows.length} чанков для ${doc.id}`);
}

async function main() {
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !OPENAI_API_KEY) {
    console.error('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / OPENAI_API_KEY не заданы');
    process.exit(1);
  }

  console.log('🚀 Старт manual-ingest (внутренние документы СРВТ)');
  await clearInternalDocuments();

  for (const doc of MANUAL_DOCS) {
    try {
      await ingestManualDoc(doc);
    } catch (err) {
      console.error(`Ошибка при обработке ${doc.id}:`, err);
    }
  }

  console.log('🎉 Manual-ingest завершён');
}

main().catch((err) => {
  console.error('Фатальная ошибка manual-ingest:', err);
  process.exit(1);
});

