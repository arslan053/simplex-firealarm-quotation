import { apiClient } from '@/shared/api/client';
import type {
  JobStartResponse,
  PanelAnswersResponse,
  PanelSelectionJobStatus,
  PanelSelectionResults,
} from '../types/panel-selection';

export const panelSelectionApi = {
  run: (projectId: string) =>
    apiClient.post<JobStartResponse>(
      `/projects/${projectId}/panel-selection/run`,
    ),

  getStatus: (projectId: string, jobId: string) =>
    apiClient.get<PanelSelectionJobStatus>(
      `/projects/${projectId}/panel-selection/status/${jobId}`,
    ),

  getResults: (projectId: string) =>
    apiClient.get<PanelSelectionResults>(
      `/projects/${projectId}/panel-selection/results`,
    ),

  getActiveJob: (projectId: string) =>
    apiClient.get<{ active: boolean; job_id?: string; status?: string; message?: string }>(
      `/projects/${projectId}/panel-selection/active-job`,
    ),

  getAnswers: (projectId: string) =>
    apiClient.get<PanelAnswersResponse>(
      `/projects/${projectId}/panel-selection/answers`,
    ),
};
