import { apiClient } from '@/shared/api/client';
import type { CompanySettings } from '../types';

export const settingsApi = {
  getCompanySettings: () =>
    apiClient.get<CompanySettings>('/settings/general'),

  updateTextSettings: (data: { signatory_name?: string; company_phone?: string }) =>
    apiClient.put<CompanySettings>('/settings/general', data),

  uploadLetterhead: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<CompanySettings>('/settings/general/letterhead', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteLetterhead: () =>
    apiClient.delete<CompanySettings>('/settings/general/letterhead'),

  uploadSignature: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<CompanySettings>('/settings/general/signature', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteSignature: () =>
    apiClient.delete<CompanySettings>('/settings/general/signature'),
};
