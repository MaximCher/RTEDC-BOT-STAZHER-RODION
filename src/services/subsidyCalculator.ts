import path from 'path';
import fs from 'fs/promises';
import { SubsidyInput, SubsidyProgram, SubsidyResult } from '../types/subsidy';
import { logger } from '../utils/logger';

let cache: SubsidyProgram[] | null = null;
let lastLoadFailed = false;

const candidatePaths = [
  path.resolve(__dirname, '..', 'data', 'subsidies.json'),
  path.resolve(process.cwd(), 'src', 'data', 'subsidies.json')
];

const loadPrograms = async (): Promise<SubsidyProgram[]> => {
  if (cache) {
    return cache;
  }

  for (const candidate of candidatePaths) {
    try {
      const fileContent = await fs.readFile(candidate, 'utf-8');
      const parsed = JSON.parse(fileContent);
      if (!Array.isArray(parsed)) {
        throw new Error('subsidies.json must be an array');
      }
      cache = parsed as SubsidyProgram[];
      lastLoadFailed = false;
      return cache;
    } catch (error) {
      logger.error('Failed to load subsidy rules', {
        path: candidate,
        error: error instanceof Error ? { message: error.message, stack: error.stack } : error
      });
    }
  }

  lastLoadFailed = true;
  cache = [];
  return cache;
};

const matchProgram = (program: SubsidyProgram, input: SubsidyInput): boolean => {
  const fitsForm = program.forms.includes(input.entityType);
  const fitsExport = !program.requiresExport || input.hasExport;
  const fitsCost =
    program.costTypes.includes(input.costType) || program.costTypes.includes('other');
  const normalizedRegion = input.region.toLowerCase();
  const fitsRegion =
    normalizedRegion === 'all' ||
    program.regions.includes('all') ||
    program.regions.some((region) => region.toLowerCase() === normalizedRegion);
  const withinSpend =
    input.spend >= program.minSpend &&
    (typeof program.maxSpend === 'undefined' || input.spend <= program.maxSpend);

  return fitsForm && fitsExport && fitsCost && fitsRegion && withinSpend;
};

export const applyFormula = (program: SubsidyProgram, input: SubsidyInput): number => {
  const bonus = input.hasExport ? program.bonusForExport ?? 0 : 0;
  const effectiveCoverage = Math.min(program.coverageRate + bonus, 0.9);
  const raw = input.spend * effectiveCoverage;
  return Math.min(program.maxAmount, Math.round(raw));
};

export const calculateSubsidies = async (
  input: SubsidyInput
): Promise<SubsidyResult[]> => {
  const programs = await loadPrograms();
  const matches = programs.filter((program) => matchProgram(program, input));

  return matches.map((program) => {
    const estimatedAmount = applyFormula(program, input);
    const coveragePercent =
      (program.coverageRate + (input.hasExport ? program.bonusForExport ?? 0 : 0)) * 100;
    return {
      programId: program.id,
      title: program.title,
      description: program.description,
      estimatedAmount,
      notes: `Покрытие до ${coveragePercent.toFixed(0)}% (потолок ${program.maxAmount.toLocaleString(
        'ru-RU'
      )} ₽)`
    };
  });
};

export const didSubsidyLoadFail = (): boolean => lastLoadFailed;
