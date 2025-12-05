import { SubsidyProgram as PrismaSubsidyProgram } from '@prisma/client';
import { prisma } from './db';
import { SubsidyProgram } from '../types/subsidy';
import { logger } from '../utils/logger';

export interface RawSubsidyProgram {
  code: string;
  title: string;
  description: string;
  sectors: string[];
  costTypes: string[];
  regions: string[];
  keywords?: string[];
  isExport?: boolean;
  minBudget?: number;
  maxBudget?: number;
  coverageRate?: number;
  maxAmount?: number;
  conditions?: string;
  recipient?: string;
  docsRequired?: string;
  notes?: string;
}

const normalizeValues = (values: string[]): string[] =>
  Array.from(
    new Set(
      values
        .map((value) => value.trim())
        .filter(Boolean)
    )
  );

const mapRecordToProgram = (record: PrismaSubsidyProgram): SubsidyProgram => ({
  id: record.id,
  code: record.code,
  title: record.title,
  description: record.description,
  sectors: record.sectors,
  costTypes: record.costTypes,
  regions: record.regions,
  keywords: record.keywords,
  isExport: record.isExport,
  minBudget: record.minBudget ?? undefined,
  maxBudget: record.maxBudget ?? undefined,
  coverageRate: record.coverageRate ?? undefined,
  maxAmount: record.maxAmount ?? undefined,
  conditions: record.conditions ?? undefined,
  recipient: record.recipient ?? undefined,
  docsRequired: record.docsRequired ?? undefined,
  notes: record.notes ?? undefined
});

const sanitizeNumber = (value?: number): number | undefined =>
  typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : undefined;

const sanitizeRatio = (value?: number): number | undefined => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return undefined;
  }
  return Math.max(0, Math.min(1, value));
};

export const getAllPrograms = async (): Promise<SubsidyProgram[]> => {
  const records = await prisma.subsidyProgram.findMany({
    orderBy: [{ title: 'asc' }]
  });
  return records.map(mapRecordToProgram);
};

export const upsertPrograms = async (programs: RawSubsidyProgram[]): Promise<void> => {
  if (!programs.length) {
    logger.warn('No subsidy programs provided for import');
    return;
  }

  const operations = programs.map((program) => {
    const data = {
      code: program.code.trim(),
      title: program.title.trim(),
      description: program.description.trim(),
      sectors: normalizeValues(program.sectors.length ? program.sectors : ['other']),
      costTypes: normalizeValues(program.costTypes.length ? program.costTypes : ['other']),
      regions: normalizeValues(program.regions.length ? program.regions : ['other']),
      keywords: normalizeValues(program.keywords ?? []),
      isExport: Boolean(program.isExport),
      minBudget: sanitizeNumber(program.minBudget) ?? null,
      maxBudget: sanitizeNumber(program.maxBudget) ?? null,
      coverageRate: sanitizeRatio(program.coverageRate) ?? null,
      maxAmount: sanitizeNumber(program.maxAmount) ?? null,
      conditions: program.conditions?.trim() || null,
      recipient: program.recipient?.trim() || null,
      docsRequired: program.docsRequired?.trim() || null,
      notes: program.notes?.trim() || null
    };

    return prisma.subsidyProgram.upsert({
      where: { code: data.code },
      create: data,
      update: data
    });
  });

  await prisma.$transaction(operations);
  logger.info('subsidy_programs_upserted', { count: programs.length });
};

