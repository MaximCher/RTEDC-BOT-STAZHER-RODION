import { Direction } from './lead';

export type EntityType = 'ИП' | 'ООО' | 'Самозанятый';

export type SubsidyCostType =
  | 'logistics'
  | 'exhibitions'
  | 'certification'
  | 'development'
  | 'payments'
  | 'other';

export interface SubsidyProgram {
  id: string;
  title: string;
  description: string;
  direction: Direction;
  forms: EntityType[];
  requiresExport: boolean;
  costTypes: SubsidyCostType[];
  regions: string[];
  minSpend: number;
  maxSpend?: number;
  maxAmount: number;
  coverageRate: number;
  bonusForExport?: number;
}

export interface SubsidyInput {
  entityType: EntityType;
  hasExport: boolean;
  costType: SubsidyCostType;
  spend: number;
  region: string;
}

export interface SubsidyResult {
  programId: string;
  title: string;
  description: string;
  estimatedAmount: number;
  notes: string;
}
