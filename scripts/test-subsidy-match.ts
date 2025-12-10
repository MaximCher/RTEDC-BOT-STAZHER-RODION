import 'dotenv/config';
import { detectCompanySectorFromText } from '../src/services/subsidies/companyProfile';
import { matchSubsidies } from '../src/services/subsidies/matchSubsidies';

async function main() {
  const text = 'айти 1.5кк развитие мск';
  const sector = detectCompanySectorFromText(text);

  const result = await matchSubsidies({
    sector,
    regionCode: 'Москва',
    budgetRub: 1_500_000
  });

  console.log('sector =', sector);
  console.log(
    result.map((r) => ({
      title: r.program.title,
      sectors: r.program.sectors,
      score: r.score
    }))
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

