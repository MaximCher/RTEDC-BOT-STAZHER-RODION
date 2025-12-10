import 'dotenv/config';
import { searchSrvtRag } from '../src/services/vectorSearch';

async function main() {
  const chunks = await searchSrvtRag('информация о компании HP', {
    minSimilarity: 0.0,
    matchCount: 5,
  });
  console.log(chunks);
}

main();
