import { SubsidyClassification, SubsidyProgram } from '../types/subsidy';
import { getAllPrograms } from './subsidyRepository';
import { fetchRemotePrograms } from './rag/ragAggregator';

const LOCAL_CACHE_TTL = 5 * 60 * 1000;

interface CacheEntry {
  data: SubsidyProgram[];
  expiresAt: number;
}

let localCache: CacheEntry | null = null;

const loadLocalPrograms = async (): Promise<SubsidyProgram[]> => {
  if (localCache && localCache.expiresAt > Date.now()) {
    return localCache.data;
  }
  const data = await getAllPrograms();
  localCache = { data, expiresAt: Date.now() + LOCAL_CACHE_TTL };
  return data;
};

export const getProgramsForClassification = async (
  classification: SubsidyClassification
): Promise<SubsidyProgram[]> => {
  const [localPrograms, remotePrograms] = await Promise.all([
    loadLocalPrograms(),
    fetchRemotePrograms(classification)
  ]);
  return mergeProgramLists(localPrograms, remotePrograms);
};

const mergeProgramLists = (
  localPrograms: SubsidyProgram[],
  remotePrograms: SubsidyProgram[]
): SubsidyProgram[] => {
  if (!remotePrograms.length) {
    return localPrograms;
  }
  const map = new Map<string, SubsidyProgram>();
  localPrograms.forEach((program) => map.set(program.code, program));
  remotePrograms.forEach((program) => {
    if (!map.has(program.code)) {
      map.set(program.code, program);
    }
  });
  return Array.from(map.values());
};

