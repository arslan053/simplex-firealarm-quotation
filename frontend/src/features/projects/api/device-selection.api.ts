import { apiClient } from '@/shared/api/client';
import type { DeviceSelectionResultsResponse } from '../types/device-selection';

export const deviceSelectionApi = {
  getResults: (projectId: string, params: { page?: number; limit?: number } = {}) =>
    apiClient.get<DeviceSelectionResultsResponse>(
      `/projects/${projectId}/device-selection/results`,
      { params: { page: params.page ?? 1, limit: params.limit ?? 20 } },
    ),
};
