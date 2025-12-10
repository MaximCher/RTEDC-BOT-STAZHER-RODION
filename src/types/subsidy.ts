import { Direction } from './lead';

export type SubsidySector =
  | 'it'
  | 'export'
  | 'manufacturing'
  | 'logistics'
  | 'agro'
  | 'tourism'
  | 'agrotourism'
  | 'services'
  | 'construction'
  | 'education'
  | 'healthcare'
  | 'other';

export type SubsidyCostType =
  | 'logistics'
  | 'marketing'
  | 'certification'
  | 'equipment'
  | 'staff'
  | 'payroll'
  | 'r_and_d'
  | 'exhibitions'
  | 'software'
  | 'training'
  | 'other';

export type SubsidyRegionCode = 'msk' | 'spb' | 'dfo' | 'rf' | 'fo' | 'other' | 'unknown';
export type SubsidyRegion = 'moscow' | 'spb' | 'dfo' | 'fo' | 'other' | 'unknown';

export interface SubsidyClassification {
  sectors: SubsidySector[];
  costTypes: SubsidyCostType[];
  region: SubsidyRegion;
  export: boolean | null;
  budgetFrom: number | null;
  budgetTo: number | null;
  notes?: string;
  excludeSectors?: SubsidySector[];
}

export interface SubsidyProgram {
  id: number;
  code: string;
  title: string;
  description: string;
  direction?: Direction;
  sectors: string[];
  costTypes: string[];
  regions: string[];
  keywords: string[];
  isExport: boolean;
  minBudget?: number | null;
  maxBudget?: number | null;
  coverageRate?: number | null;
  maxAmount?: number | null;
  conditions?: string | null;
  recipient?: string | null;
  docsRequired?: string | null;
  notes?: string | null;
}

export interface EstimatedProgram {
  programCode: string;
  title: string;
  estimatedAmount: number;
  coveragePercent?: number;
  description?: string;
  score?: number;
  sectors?: string[];
}

export interface HybridSubsidyInput {
  classification: SubsidyClassification;
}

export interface SubsidyMatchScore {
  program: SubsidyProgram;
  score: number;
  estimatedAmount: number;
}

export interface SubsidyEstimationResult {
  programs: EstimatedProgram[];
  metadataPrograms: EstimatedProgram[];
  hasAmountEstimate: boolean;
}
