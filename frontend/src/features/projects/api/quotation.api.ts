import { apiClient } from '@/shared/api/client';
import type {
  GenerateQuotationRequest,
  InclusionQuestion,
  QuotationDownloadResponse,
  QuotationResponse,
} from '../types/quotation';

export const quotationApi = {
  generate: (projectId: string, data: GenerateQuotationRequest) =>
    apiClient.post<QuotationResponse>(
      `/projects/${projectId}/quotation/generate`,
      data,
    ),

  getInclusions: (projectId: string, serviceOption: number) =>
    apiClient.get<{ questions: InclusionQuestion[] }>(
      `/projects/${projectId}/quotation/inclusions`,
      { params: { service_option: serviceOption } },
    ),

  get: (projectId: string) =>
    apiClient.get<QuotationResponse>(`/projects/${projectId}/quotation`),

  download: (projectId: string, format: 'docx' | 'xlsx' = 'docx') =>
    apiClient.get<QuotationDownloadResponse>(
      `/projects/${projectId}/quotation/download`,
      { params: { format } },
    ),

  preview: (projectId: string) =>
    apiClient.get<Blob>(`/projects/${projectId}/quotation/preview`, {
      responseType: 'blob',
    }),
};
