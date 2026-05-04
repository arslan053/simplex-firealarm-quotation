import { apiClient } from '@/shared/api/client';
import type {
  SpecExistingCheckResponse,
  SpecUploadResponse,
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

};
