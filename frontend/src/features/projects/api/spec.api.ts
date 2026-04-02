import { apiClient } from '@/shared/api/client';
import type {
  SpecExistingCheckResponse,
  SpecUploadResponse,
  SpecBlockListResponse,
} from '../types/spec';

export const specApi = {
  checkExisting: (projectId: string) =>
    apiClient.get<SpecExistingCheckResponse>(
      `/projects/${projectId}/spec/check`,
    ),

  upload: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<SpecUploadResponse>(
      `/projects/${projectId}/spec/upload`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },

  getBlocks: (
    projectId: string,
    documentId: string,
    page: number = 1,
    limit: number = 100,
  ) =>
    apiClient.get<SpecBlockListResponse>(
      `/projects/${projectId}/spec/blocks`,
      { params: { document_id: documentId, page, limit } },
    ),
};
