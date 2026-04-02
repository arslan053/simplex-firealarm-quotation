import { apiClient } from '@/shared/api/client';
import type {
  JobStartResponse,
  SpecAnalysisJobStatus,
} from '../types/spec-analysis';

export const specAnalysisApi = {
  run: (projectId: string) =>
    apiClient.post<JobStartResponse>(
      `/projects/${projectId}/spec-analysis/run`,
    ),

  getStatus: (projectId: string, jobId: string) =>
    apiClient.get<SpecAnalysisJobStatus>(
      `/projects/${projectId}/spec-analysis/status/${jobId}`,
    ),

  getActiveJob: (projectId: string) =>
    apiClient.get<{ active: boolean; job_id?: string; status?: string; message?: string }>(
      `/projects/${projectId}/spec-analysis/active-job`,
    ),
};
