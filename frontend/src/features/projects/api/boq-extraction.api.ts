import { apiClient } from '@/shared/api/client';
import type {
  JobStartResponse,
  BoqExtractionJobStatus,
} from '../types/boq-extraction';

export const boqExtractionApi = {
  run: (projectId: string) =>
    apiClient.post<JobStartResponse>(
      `/projects/${projectId}/boq-extraction/run`,
    ),

  getStatus: (projectId: string, jobId: string) =>
    apiClient.get<BoqExtractionJobStatus>(
      `/projects/${projectId}/boq-extraction/status/${jobId}`,
    ),

  getActiveJob: (projectId: string) =>
    apiClient.get<{ active: boolean; job_id?: string; status?: string; message?: string }>(
      `/projects/${projectId}/boq-extraction/active-job`,
    ),
};
