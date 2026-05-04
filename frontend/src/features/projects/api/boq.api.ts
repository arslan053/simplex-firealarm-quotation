import { apiClient } from '@/shared/api/client';
import type { DocumentResponse } from '../types/boq';

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
