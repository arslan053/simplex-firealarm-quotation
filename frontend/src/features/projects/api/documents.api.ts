import { apiClient } from '@/shared/api/client';
import type { DocumentResponse } from '../types/boq';

export interface DocumentViewUrlResponse {
  url: string;
}

export const documentsApi = {
  listAll: (projectId: string) =>
    apiClient.get<DocumentResponse[]>(`/projects/${projectId}/documents`),

  getViewUrl: (projectId: string, documentId: string) =>
    apiClient.get<DocumentViewUrlResponse>(
      `/projects/${projectId}/documents/${documentId}/view-url`,
    ),
};
