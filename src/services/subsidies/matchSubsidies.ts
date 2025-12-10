import { SubsidyProgram } from '../../types/subsidy';
import { getAllPrograms } from '../subsidyRepository';
import {
  CompanySector,
  detectCompanySectorFromText,
  normalizeProgramSectors
} from './companyProfile';

export interface SubsidyMatchContext {
  sector: CompanySector;
  regionCode?: string;
  budgetRub?: number;
}

export interface SubsidyProgramRow {
  id: number;
  code: string;
  title: string;
  regions: string[] | null;
  sectors: string[] | null;
  minBudget?: number | null;
  maxBudget?: number | null;
  description?: string | null;
  coverageRate?: number | null;
  maxAmount?: number | null;
}

export interface SubsidyMatchResult {
  program: SubsidyProgramRow;
  score: number;
  reasons: string[];
}

const IT_EXCLUDE_PATTERNS = [/агротур/i, /сельск/i, /туризм/i, /агро/i, /ферм/i, /нефтегаз/i];

export async function matchSubsidies(ctx: SubsidyMatchContext): Promise<SubsidyMatchResult[]> {
  const programs = await getAllPrograms();
  const candidates = programs.map(mapProgramRow);
  const results: SubsidyMatchResult[] = [];

  for (const program of candidates) {
    const match = scoreProgram(program, ctx);
    if (match) {
      results.push(match);
    }
  }

  const sorted = results.sort((a, b) => b.score - a.score);
  return sorted.slice(0, 3);
}

function scoreProgram(
  program: SubsidyProgramRow,
  ctx: SubsidyMatchContext
): SubsidyMatchResult | null {
  const reasons: string[] = [];
  const programSectors = normalizeProgramSectors(program.sectors);

  if (!programSectors.length) {
    programSectors.push('other');
  }

  const sectorScore = resolveSectorScore(programSectors, ctx.sector);
  if (sectorScore < 0) {
    return null;
  }

  if (
    ctx.sector === 'it' &&
    IT_EXCLUDE_PATTERNS.some((pattern) => pattern.test(program.title ?? ''))
  ) {
    return null;
  }

  let budgetScore = 0;
  if (typeof ctx.budgetRub === 'number' && Number.isFinite(ctx.budgetRub)) {
    budgetScore = resolveBudgetScore(program, ctx.budgetRub);
    reasons.push('Бюджет сопоставим');
  }

  const regionBonus = resolveRegionBonus(program.regions, ctx.regionCode);
  const federalBonus = isFederalProgram(program.regions) ? 0.1 : 0;

  const score = sectorScore * (1 + budgetScore + regionBonus + federalBonus);

  if (score <= 0) {
    return null;
  }

  if (sectorScore >= 1) {
    reasons.push('Отрасль совпадает');
  } else if (sectorScore >= 0.3) {
    reasons.push('Программа без отраслевого ограничения');
  }
  if (regionBonus > 0) {
    reasons.push('Регион подходит');
  }
  if (federalBonus > 0) {
    reasons.push('Федеральная программа');
  }

  return { program, score, reasons };
}

function resolveSectorScore(programSectors: CompanySector[], sector: CompanySector): number {
  if (programSectors.includes(sector)) {
    return 1;
  }
  if (programSectors.includes('other') || programSectors.length === 0) {
    return 0.3;
  }
  return -Infinity;
}

function resolveBudgetScore(program: SubsidyProgramRow, budgetRub: number): number {
  const min = program.minBudget ?? null;
  const max = program.maxBudget ?? null;
  if (min === null && max === null) {
    return 0.2;
  }
  if (min !== null && budgetRub < min) {
    return budgetRub >= min * 0.8 ? 0.1 : -0.5;
  }
  if (max !== null && budgetRub > max) {
    return budgetRub <= max * 1.2 ? 0.1 : -0.2;
  }
  if (min !== null && max !== null) {
    const center = (min + max) / 2;
    const range = max - min || 1;
    const diff = Math.abs(budgetRub - center);
    const proximity = Math.max(0, 1 - diff / range);
    return 0.2 + 0.5 * proximity;
  }
  return 0.3;
}

function resolveRegionBonus(regions: string[] | null, regionCode?: string): number {
  if (!regionCode) {
    return 0;
  }
  const normalizedRegion = normalizeRegion(regionCode);
  if (!normalizedRegion) {
    return 0;
  }
  if (!regions || regions.length === 0) {
    return 0.1;
  }
  const normalizedRegions = regions.map((r) => normalizeRegion(r)).filter(Boolean);
  if (normalizedRegions.includes(normalizedRegion)) {
    return 0.2;
  }
  if (normalizedRegions.some((r) => r === 'rf' || r === 'all')) {
    return 0.1;
  }
  return 0;
}

function isFederalProgram(regions: string[] | null): boolean {
  if (!regions || regions.length === 0) {
    return true;
  }
  return regions.some((r) => {
    const n = normalizeRegion(r);
    return n === 'rf' || n === 'all';
  });
}

function normalizeRegion(region: string | undefined | null): string | null {
  if (!region) return null;
  const val = region.toLowerCase();
  if (['msk', 'moscow', 'москва', 'московская область', 'мо'].some((r) => val.includes(r))) {
    return 'msk';
  }
  if (['spb', 'питер', 'санкт'].some((r) => val.includes(r))) {
    return 'spb';
  }
  if (['дфо', 'дальн', 'владивост', 'сахалин', 'камчат'].some((r) => val.includes(r))) {
    return 'dfo';
  }
  if (['rf', 'росси', 'вся страна', 'федерал'].some((r) => val.includes(r))) {
    return 'rf';
  }
  return val.trim() || null;
}

function mapProgramRow(program: SubsidyProgram): SubsidyProgramRow {
  return {
    id: program.id,
    code: program.code,
    title: program.title,
    regions: program.regions ?? null,
    sectors: program.sectors ?? null,
    minBudget: program.minBudget ?? null,
    maxBudget: program.maxBudget ?? null,
    description: program.description ?? null,
    coverageRate: program.coverageRate ?? null,
    maxAmount: program.maxAmount ?? null
  };
}

export function detectSectorFromClassificationText(text: string): CompanySector {
  return detectCompanySectorFromText(text);
}

