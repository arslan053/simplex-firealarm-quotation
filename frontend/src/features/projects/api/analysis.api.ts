import { apiClient } from '@/shared/api/client';
import type { AnalysisResultResponse } from '../types/analysis';

export const analysisApi = {
  getResults: (projectId: string) =>
    apiClient.get<AnalysisResultResponse>(
      `/projects/${projectId}/analysis/results`,
    ),

  overrideProtocol: (projectId: string, protocol: string) =>
    apiClient.put<{ protocol: string; message: string }>(
      `/projects/${projectId}/analysis/protocol`,
      { protocol },
    ),
};
