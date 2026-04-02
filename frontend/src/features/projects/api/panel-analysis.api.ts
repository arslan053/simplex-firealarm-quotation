import { apiClient } from '@/shared/api/client';
import type { PanelAnalysisResultResponse } from '../types/panel-analysis';

export const panelAnalysisApi = {
  getResults: (projectId: string) =>
    apiClient.get<PanelAnalysisResultResponse>(
      `/projects/${projectId}/panel-analysis/results`,
    ),
};
