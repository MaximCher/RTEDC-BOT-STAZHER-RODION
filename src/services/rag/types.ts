export interface RagProgramRecord {
  code: string;
  title: string;
  description: string;
  sectors: string[];
  costTypes: string[];
  regions: string[];
  keywords: string[];
  isExport: boolean;
  minBudget?: number | null;
  maxBudget?: number | null;
  coverageRate?: number | null;
  maxAmount?: number | null;
  recipient?: string | null;
  docsRequired?: string | null;
  conditions?: string | null;
  sourceUrl?: string | null;
  source: string;
  freshnessScore?: number;
  notes?: string | null;
  links?: string[];
}

