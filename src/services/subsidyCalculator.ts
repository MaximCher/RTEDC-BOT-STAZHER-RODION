import {
  EstimatedProgram,
  SubsidyClassification,
  SubsidyEstimationResult,
  SubsidyProgram,
  SubsidyRegion
} from '../types/subsidy';
import { logger } from '../utils/logger';
import {
  CompanySector,
  normalizeProgramSectors
} from './subsidies/companyProfile';
import {
  matchSubsidies,
  SubsidyMatchContext,
  SubsidyMatchResult
} from './subsidies/matchSubsidies';

// Подбор программ: берём SubsidyProgram из Postgres, жёстко фильтруем по отрасли (CompanySector),
// отбрасываем несоответствующие бюджету/региону, начисляем бонусы за регион/федеральность,
// сортируем по score и отдаём TOP-3. Для IT дополнительно удаляются агро/туризм/сельск.

export const calculateSubsidyResult = async (
  classification: SubsidyClassification
): Promise<SubsidyEstimationResult> => {
  const ctx = buildMatchContext(classification);
  const matches = await matchSubsidies(ctx);

  if (!matches.length) {
    logger.info('subsidy_matches_empty', { classification, ctx });
  }

  const budgetRange = resolveBudgetRange(classification);
  const estimated = matches.map((match) => toEstimatedProgram(match, budgetRange));
  const positivePrograms = estimated.filter((program) => program.estimatedAmount > 0);

  return {
    programs: (positivePrograms.length ? positivePrograms : estimated).slice(0, 3),
    metadataPrograms: estimated,
    hasAmountEstimate: positivePrograms.length > 0
  };
};

export const computeEstimatedAmount = (
  program: Pick<SubsidyProgram, 'minBudget' | 'maxAmount' | 'coverageRate' | 'maxBudget'>,
  range: BudgetRange
): number => {
  const targetBudget = range.point ?? range.max ?? range.min ?? program.minBudget ?? program.maxAmount ?? 1_000_000;

  if (!targetBudget || targetBudget <= 0) {
    return program.maxAmount ?? 0;
  }

  if (!program.coverageRate || program.coverageRate <= 0) {
    if (program.maxAmount && program.maxAmount > 0) {
      return Math.min(program.maxAmount, targetBudget);
    }
    return 0;
  }

  const base = Math.round(targetBudget * program.coverageRate);
  const capped = program.maxAmount ? Math.min(base, program.maxAmount) : base;
  return capped;
};

const toEstimatedProgram = (match: SubsidyMatchResult, range: BudgetRange): EstimatedProgram => {
  const estimatedAmount = computeEstimatedAmount(match.program, range);
  return {
    programCode: match.program.code,
    title: match.program.title,
    estimatedAmount,
    coveragePercent: match.program.coverageRate
      ? Math.round((match.program.coverageRate ?? 0) * 100)
      : undefined,
    description: (match.program.description ?? '').split('\n')[0]?.trim(),
    score: match.score,
    sectors: normalizeProgramSectors(match.program.sectors)
  };
};

interface BudgetRange {
  min: number | null;
  max: number | null;
  point: number | null;
}

const resolveBudgetRange = (classification: SubsidyClassification): BudgetRange => ({
  min:
    typeof classification.budgetFrom === 'number' && Number.isFinite(classification.budgetFrom)
      ? classification.budgetFrom
      : null,
  max:
    typeof classification.budgetTo === 'number' && Number.isFinite(classification.budgetTo)
      ? classification.budgetTo
      : null,
  point:
    typeof classification.budgetTo === 'number' && Number.isFinite(classification.budgetTo)
      ? classification.budgetTo
      : typeof classification.budgetFrom === 'number' && Number.isFinite(classification.budgetFrom)
        ? classification.budgetFrom
        : null
});

const rangesOverlap = (
  wantMin: number | null,
  wantMax: number | null,
  programMin: number | null,
  programMax: number | null
): boolean => {
  const min = wantMin ?? wantMax ?? null;
  const max = wantMax ?? wantMin ?? null;

  if (min === null && max === null) {
    return true;
  }

  if (programMin === null && programMax === null) {
    return true;
  }

  const desiredMin = min ?? max ?? 0;
  const desiredMax = max ?? min ?? desiredMin;
  const progMin = programMin ?? 0;
  const progMax = programMax ?? Number.MAX_SAFE_INTEGER;

  return desiredMax >= progMin && desiredMin <= progMax;
};

const mapRegionToProgramCode = (region: SubsidyRegion): string => {
  switch (region) {
    case 'moscow':
      return 'msk';
    case 'spb':
      return 'spb';
    case 'dfo':
      return 'dfo';
    case 'fo':
      return 'rf';
    case 'other':
      return 'other';
    default:
      return '';
  }
};

const buildMatchContext = (classification: SubsidyClassification): SubsidyMatchContext => {
  const sector = toCompanySector(classification.sectors?.[0]);
  const regionCode = mapRegionToProgramCode(classification.region);
  const budgetRub =
    (typeof classification.budgetTo === 'number' && classification.budgetTo > 0
      ? classification.budgetTo
      : null) ??
    (typeof classification.budgetFrom === 'number' && classification.budgetFrom > 0
      ? classification.budgetFrom
      : null) ??
    undefined;

  return {
    sector,
    regionCode,
    budgetRub
  };
};

const toCompanySector = (sector?: string): CompanySector => {
  const normalized = (sector ?? '').toLowerCase();
  if (normalizeProgramSectors([normalized]).includes('it')) return 'it';
  if (normalizeProgramSectors([normalized]).includes('logistics')) return 'logistics';
  if (normalizeProgramSectors([normalized]).includes('agro')) return 'agro';
  if (normalizeProgramSectors([normalized]).includes('tourism')) return 'tourism';
  if (normalizeProgramSectors([normalized]).includes('finance')) return 'finance';
  if (normalizeProgramSectors([normalized]).includes('industry')) return 'industry';
  return 'other';
};
