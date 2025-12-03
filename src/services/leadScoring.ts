import { Direction } from '../types/lead';
import { SubsidyInput } from '../types/subsidy';

export interface ExtendedLeadContext {
  scenario: string;
  direction: Direction;
  metadata?: Record<string, unknown>;
}

export interface LeadScoringResult {
  baseScore: number;
  extendedScore: number;
  factors: string[];
}

const HOT_QUIZ_VALUES = new Set([
  'working-capital',
  'expansion',
  'hard-currency',
  'routes',
  'grants',
  'size_large',
  'region_asia',
  'region_me',
  'target_asia',
  'target_mea'
]);

const clampScore = (value: number, min = 1, max = 5): number =>
  Math.max(min, Math.min(max, value));

export const calculateLeadScoreDetails = ({
  scenario,
  direction,
  metadata
}: ExtendedLeadContext): LeadScoringResult => {
  const normalizedMeta = metadata ?? {};
  const baseScore = baseScenarioScore(scenario, normalizedMeta);
  const { bonus, factors } = extractBonusFactors(direction, normalizedMeta);
  const extendedScore = clampScore(baseScore + bonus);
  return { baseScore, extendedScore, factors };
};

export const computeLeadScore = (context: ExtendedLeadContext): number =>
  calculateLeadScoreDetails(context).extendedScore;

const baseScenarioScore = (scenario: string, metadata: Record<string, unknown>): number => {
  if (scenario === 'quiz_help') {
    return inferQuizScore(metadata);
  }
  if (scenario === 'subsidy_application') {
    return inferSubsidyScore(metadata);
  }
  if (scenario === 'case_review') {
    return 2;
  }
  if (scenario === 'manager_contact') {
    return 2;
  }
  if (scenario.startsWith('service_')) {
    return 2;
  }
  return 1;
};

const inferQuizScore = (metadata: Record<string, unknown>): number => {
  const answers = metadata.answers;
  if (answers && typeof answers === 'object') {
    const values = Object.values(answers as Record<string, unknown>).map((v) => String(v));
    if (values.some((value) => HOT_QUIZ_VALUES.has(value))) {
      return 3;
    }
  }
  return 2;
};

const inferSubsidyScore = (metadata: Record<string, unknown>): number => {
  const input = metadata.input as SubsidyInput | undefined;
  if (input && typeof input.spend === 'number' && input.spend >= 3_000_000) {
    return 3;
  }
  return 2;
};

const extractBonusFactors = (
  direction: Direction,
  metadata: Record<string, unknown>
): { bonus: number; factors: string[] } => {
  let bonus = 0;
  const factors: string[] = [];

  const spend = extractSpend(metadata);
  if (spend >= 5_000_000) {
    bonus += 2;
    factors.push('high_spend');
  } else if (spend >= 1_000_000) {
    bonus += 1;
    factors.push('mid_spend');
  }

  if (extractHasExport(metadata)) {
    bonus += 1;
    factors.push('export_pipeline');
  }

  if (containsOpportunityRegion(metadata)) {
    bonus += 1;
    factors.push('priority_market');
  }

  if (containsRiskKeywords(metadata, direction)) {
    bonus += 1;
    factors.push('risk_alert');
  }

  return { bonus, factors };
};

const extractSpend = (metadata: Record<string, unknown>): number => {
  const input = metadata.input as SubsidyInput | undefined;
  if (input && typeof input.spend === 'number') {
    return input.spend;
  }
  const spendValue = metadata.spend;
  if (typeof spendValue === 'number') {
    return spendValue;
  }
  return 0;
};

const extractHasExport = (metadata: Record<string, unknown>): boolean => {
  const input = metadata.input as SubsidyInput | undefined;
  if (input && typeof input.hasExport === 'boolean') {
    return input.hasExport;
  }
  const hasExport = metadata.hasExport;
  return typeof hasExport === 'boolean' ? hasExport : false;
};

const containsOpportunityRegion = (metadata: Record<string, unknown>): boolean => {
  const regionCandidates = [
    metadata.region,
    metadata.targetRegion,
    metadata.market,
    metadata.target
  ]
    .concat(
      metadata.results && Array.isArray(metadata.results)
        ? metadata.results.map((result) => {
            if (result && typeof result === 'object' && 'region' in result) {
              return (result as Record<string, unknown>).region;
            }
            return undefined;
          })
        : []
    )
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());

  const keywords = ['китай', 'asia', 'оаэ', 'dubai', 'европа', 'eu', 'turkey', 'ksa'];
  return regionCandidates.some((region) =>
    keywords.some((keyword) => region.includes(keyword))
  );
};

const containsRiskKeywords = (metadata: Record<string, unknown>, direction: Direction): boolean => {
  const textFields = [
    metadata.summary,
    metadata.text,
    metadata.problem,
    metadata.advice,
    metadata.description
  ]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase())
    .join(' ');

  const riskKeywords = ['блокир', 'спор', 'не плат', 'санк', 'штраф', 'срыв', 'замороз'];
  const directionKeywords: Record<Direction, string[]> = {
    finance: ['кассовый разрыв', 'процент', 'пени'],
    logistics: ['застрял', 'порт', 'тамож'],
    payments: ['bank', 'swift', 'compliance'],
    analytics: ['риски', 'проверка', 'due'],
    other: ['срочно', 'горит']
  };

  const keywords = riskKeywords.concat(directionKeywords[direction]);
  return keywords.some((keyword) => textFields.includes(keyword));
};

