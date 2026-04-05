import { apiClient } from '@/shared/api/client';
import type {
  JobStartResponse,
  DeviceSelectionJobStatus,
  DeviceSelectionResultsResponse,
} from '../types/device-selection';

export const deviceSelectionApi = {
  run: (projectId: string) =>
    apiClient.post<JobStartResponse>(
      `/projects/${projectId}/device-selection/run`,
    ),

  getStatus: (projectId: string, jobId: string) =>
    apiClient.get<DeviceSelectionJobStatus>(
      `/projects/${projectId}/device-selection/status/${jobId}`,
    ),

  getResults: (projectId: string, params: { page?: number; limit?: number } = {}) =>
    apiClient.get<DeviceSelectionResultsResponse>(
      `/projects/${projectId}/device-selection/results`,
      { params: { page: params.page ?? 1, limit: params.limit ?? 20 } },
    ),

  getActiveJob: (projectId: string) =>
    apiClient.get<{ active: boolean; job_id?: string; status?: string; message?: string }>(
      `/projects/${projectId}/device-selection/active-job`,
    ),

  overrideNetworkType: (projectId: string, networkType: string) =>
    apiClient.put<{ network_type: string; message: string }>(
      `/projects/${projectId}/device-selection/network-type`,
      { network_type: networkType },
    ),
};
