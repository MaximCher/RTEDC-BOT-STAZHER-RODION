/* eslint-disable @typescript-eslint/no-var-requires */
// Полифил File нужен самым первым (до любых импортов, тянущих undici/fetch).
const { Blob: NodeBlob } = require('buffer') as { Blob: typeof globalThis.Blob };
if (typeof (globalThis as { File?: unknown }).File === 'undefined') {
  class FilePolyfill extends NodeBlob {
    name: string;
    lastModified: number;
    constructor(bits: BlobPart[], name: string, options: { type?: string; lastModified?: number } = {}) {
      super(bits, options);
      this.name = name;
      this.lastModified = options.lastModified ?? Date.now();
    }
  }
  (globalThis as { File?: unknown }).File = FilePolyfill;
}

require('dotenv/config');

const axios = require('axios') as typeof import('axios').default;
const cheerio = require('cheerio') as typeof import('cheerio');

type OpenAIClient = {
  embeddings: {
    create: (args: { model: string; input: string[] }) => Promise<{ data: { embedding: number[] }[] }>;
  };
};

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Гарантируем наличие File до динамического импорта OpenAI (undici ожидает File).
(() => {
  if (typeof (globalThis as { File?: unknown }).File === 'undefined') {
    const BlobCtor: typeof Blob =
      typeof Blob !== 'undefined'
        ? Blob
        : // eslint-disable-next-line @typescript-eslint/no-var-requires
          require('buffer').Blob;

    class FilePolyfill extends BlobCtor {
      name: string;
      lastModified: number;
      constructor(bits: BlobPart[], name: string, options: { type?: string; lastModified?: number } = {}) {
        super(bits, options);
        this.name = name;
        this.lastModified = options.lastModified ?? Date.now();
      }
    }

    (globalThis as { File?: unknown }).File = FilePolyfill;
  }
})();

if (!process.env.OPENAI_API_KEY) {
  console.error('OPENAI_API_KEY не задан в .env');
  process.exit(1);
}

let openaiClient: OpenAIClient | null = null;

const getOpenAI = async (): Promise<OpenAIClient> => {
  if (openaiClient) return openaiClient;
  const OpenAI = (await import('openai')).default;
  openaiClient = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY
  });
  return openaiClient;
};

type DocumentRow = {
  source: string;
  url: string;
  content: string;
  chunk_index: number;
  embedding: number[];
};

const SRVT_PAGES: string[] = [
  'https://www.xn--b1a1acg.xn--p1ai/',
  'https://www.xn--b1a1acg.xn--p1ai/transactions',
  'https://www.xn--b1a1acg.xn--p1ai/logist',
  'https://www.xn--b1a1acg.xn--p1ai/fin',
  'https://www.xn--b1a1acg.xn--p1ai/translation',
  'https://www.xn--b1a1acg.xn--p1ai/academy',
  'https://www.xn--b1a1acg.xn--p1ai/partners',
  'https://www.xn--b1a1acg.xn--p1ai/111'
];

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

  const openai = await getOpenAI();
  const res = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: texts
  });

  return res.data.map((item) => item.embedding);
}

async function fetchPageText(url: string): Promise<string> {
  const response = await axios.get<string>(url, { responseType: 'text' });
  const $ = cheerio.load(response.data);

  const mainText = $('main').text();
  const bodyText = $('body').text();

  const text = (mainText || bodyText || '').replace(/\s+/g, ' ').trim();
  return text;
}

async function insertDocuments(rows: DocumentRow[]): Promise<void> {
  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error('SUPABASE_URL или SUPABASE_SERVICE_ROLE_KEY не заданы');
  }

  const endpoint = `${supabaseUrl}/rest/v1/documents`;

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
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

async function ingestPage(url: string): Promise<void> {
  console.log(`>>> Обрабатываю: ${url}`);

  let pageText: string;
  try {
    pageText = await fetchPageText(url);
  } catch (error) {
    console.error(`Ошибка загрузки страницы ${url}:`, error);
    return;
  }

  if (!pageText) {
    console.warn(`Пустой текст со страницы ${url}, пропускаю`);
    return;
  }

  let cleaned = pageText;

  // Удаляем <script>...</script> и <style>...</style>
  cleaned = cleaned
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ');

  // Удаляем явные CSS/JS конструкции и тильда-мусор
  cleaned = cleaned
    .replace(/#[a-z0-9\-_]+/gi, ' ')
    .replace(/\.[a-z0-9\-_]+/gi, ' ')
    .replace(/\{[\s\S]*?\}/g, ' ')
    .replace(/t_onReady[\s\S]*?;/gi, ' ')
    .replace(/t_onFuncLoad[\s\S]*?;/gi, ' ')
    .replace(/tilda[^ \n]*/gi, ' ')
    .replace(/function\s+[a-zA-Z0-9_]+\s*\([\s\S]*?\}/g, ' ');

  cleaned = cleaned.replace(/\s{2,}/g, ' ').trim();

  if (!cleaned) {
    console.warn(`После очистки текст страницы ${url} пустой, пропускаю`);
    return;
  }

  const chunks = chunkText(cleaned);
  console.log(`Текст страницы ${url} порезан на ${chunks.length} чанков`);

  const batchSize = 20;

  for (let i = 0; i < chunks.length; i += batchSize) {
    const batch = chunks.slice(i, i + batchSize);

    let embeddings: number[][];
    try {
      embeddings = await embedBatch(batch);
    } catch (error) {
      console.error(`Ошибка эмбеддингов для ${url} (чанки ${i}–${i + batch.length}):`, error);
      continue;
    }

    const rows = batch.map((content, idx) => ({
      source: 'srvt.rf',
      url,
      content,
      chunk_index: i + idx,
      embedding: embeddings[idx]
    }));

    try {
      await insertDocuments(rows);
      console.log(`Вставлено ${rows.length} чанков для ${url}, batch ${i}–${i + rows.length}`);
    } catch (error) {
      console.error(`Ошибка вставки чанков для ${url}, batch starting at ${i}:`, error);
    }
  }
}

async function main() {
  console.log('🚀 Старт ингерста SRVT страниц');

  for (const url of SRVT_PAGES) {
    try {
      await ingestPage(url);
    } catch (error) {
      console.error(`Критическая ошибка при обработке ${url}:`, error);
    }
  }

  console.log('✅ Ингест SRVT завершён');
}

main().catch((error) => {
  console.error('Фатальная ошибка скрипта srvt-ingest:', error);
  process.exit(1);
});

