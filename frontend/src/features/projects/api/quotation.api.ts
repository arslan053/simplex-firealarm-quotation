import { apiClient } from '@/shared/api/client';
import type {
  GenerateQuotationRequest,
  QuotationDownloadResponse,
  QuotationResponse,
} from '../types/quotation';

export const quotationApi = {
  generate: (projectId: string, data: GenerateQuotationRequest) =>
    apiClient.post<QuotationResponse>(
      `/projects/${projectId}/quotation/generate`,
      data,
    ),

  get: (projectId: string) =>
    apiClient.get<QuotationResponse>(`/projects/${projectId}/quotation`),

  download: (projectId: string) =>
    apiClient.get<QuotationDownloadResponse>(
      `/projects/${projectId}/quotation/download`,
    ),

  preview: (projectId: string) =>
    apiClient.get<Blob>(`/projects/${projectId}/quotation/preview`, {
      responseType: 'blob',
    }),
};
