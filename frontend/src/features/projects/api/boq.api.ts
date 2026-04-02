import { apiClient } from '@/shared/api/client';
import type {
  BoqItemListResponse,
  BoqItemResponse,
  DocumentResponse,
} from '../types/boq';

export const boqApi = {
  upload: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<DocumentResponse>(
      `/projects/${projectId}/boq/upload`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },

  listItems: (projectId: string, params: { page?: number; limit?: number } = {}) =>
    apiClient.get<BoqItemListResponse>(`/projects/${projectId}/boq/items`, {
      params: {
        page: params.page ?? 1,
        limit: params.limit ?? 50,
      },
    }),

  toggleVisibility: (projectId: string, itemId: string, isHidden: boolean) =>
    apiClient.patch<BoqItemResponse>(
      `/projects/${projectId}/boq/items/${itemId}/visibility`,
      { is_hidden: isHidden },
    ),

  listDocuments: (projectId: string) =>
    apiClient.get<DocumentResponse[]>(`/projects/${projectId}/boq/documents`),

  uploadPdf: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<DocumentResponse>(
      `/projects/${projectId}/boq/upload-pdf`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },

  uploadImages: (projectId: string, files: File[]) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    return apiClient.post<DocumentResponse>(
      `/projects/${projectId}/boq/upload-images`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },
};
