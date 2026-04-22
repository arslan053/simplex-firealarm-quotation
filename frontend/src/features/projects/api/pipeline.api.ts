import { apiClient } from '@/shared/api/client';
import type {
  PipelineStatus,
  StartPipelineResponse,
  QuotationConfigData,
  OverridesData,
} from '../types/pipeline';

export const pipelineApi = {
  start: (projectId: string) =>
    apiClient.post<StartPipelineResponse>(
      `/projects/${projectId}/pipeline/run`,
    ),

  getStatus: (projectId: string) =>
    apiClient.get<PipelineStatus>(
      `/projects/${projectId}/pipeline/status`,
    ),

  retry: (projectId: string) =>
    apiClient.post<StartPipelineResponse>(
      `/projects/${projectId}/pipeline/retry`,
    ),

  saveQuotationConfig: (projectId: string, data: QuotationConfigData) =>
    apiClient.post<{ quotation_config: QuotationConfigData }>(
      `/projects/${projectId}/pipeline/quotation-config`,
      data,
    ),

  getQuotationConfig: (projectId: string) =>
    apiClient.get<{ quotation_config: QuotationConfigData | null }>(
      `/projects/${projectId}/pipeline/quotation-config`,
    ),

  saveOverrides: (projectId: string, data: OverridesData) =>
    apiClient.patch<OverridesData>(
      `/projects/${projectId}/pipeline/overrides`,
      data,
    ),
};
