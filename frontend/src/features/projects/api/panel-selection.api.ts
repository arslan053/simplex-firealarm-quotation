import { apiClient } from '@/shared/api/client';
import type {
  PanelAnswersResponse,
  PanelSelectionResults,
} from '../types/panel-selection';

export const panelSelectionApi = {
  getResults: (projectId: string) =>
    apiClient.get<PanelSelectionResults>(
      `/projects/${projectId}/panel-selection/results`,
    ),

  getAnswers: (projectId: string) =>
    apiClient.get<PanelAnswersResponse>(
      `/projects/${projectId}/panel-selection/answers`,
    ),
};
