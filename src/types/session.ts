import { LeadPayload, Direction } from './lead';
import { SubsidyInput, SubsidyResult } from './subsidy';

export type FlowName =
  | 'idle'
  | 'quiz'
  | 'lead_form'
  | 'case_review'
  | 'subsidy'
  | 'manager_contact';

export interface QuizState {
  direction?: Direction;
  stage: 'primary' | 'followup' | 'done';
  answers: Record<string, string>;
}

export type LeadFormStep = 'name' | 'phone' | 'company' | 'confirm';

export interface LeadFormState {
  scenario: string;
  direction: Direction;
  step: LeadFormStep;
  lead: Partial<LeadPayload> & Pick<LeadPayload, 'source' | 'scenario' | 'direction' | 'userId'>;
  metadata?: Record<string, unknown>;
}

export interface CaseReviewState {
  rawText?: string;
  classification?: Direction;
}

export interface CaseInsight {
  text: string;
  direction: Direction;
  summary: string;
  advice: string;
  sources?: string[];
}

export interface QuizInsight {
  direction: Direction;
  summary: string;
  answers: Record<string, string>;
}

export type SubsidyFormStep =
  | 'entity'
  | 'export'
  | 'cost'
  | 'amount'
  | 'region'
  | 'result';

export interface SubsidyFormState {
  step: SubsidyFormStep;
  draft: Partial<SubsidyInput> & { spendRangeLabel?: string };
}

export interface SessionData {
  flow: FlowName;
  quiz?: QuizState;
  leadForm?: LeadFormState;
  caseReview?: CaseReviewState;
  subsidy?: SubsidyFormState;
  lastSubsidyRecommendation?: {
    input: SubsidyInput;
    results: SubsidyResult[];
    spendRangeLabel?: string;
    summary?: string;
  };
  lastCase?: CaseInsight;
  lastQuiz?: QuizInsight;
}

export const initialSessionState = (): SessionData => ({
  flow: 'idle'
});
