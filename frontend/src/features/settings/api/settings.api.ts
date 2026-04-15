import { apiClient } from '@/shared/api/client';
import type { CompanySettings } from '../types';

export const settingsApi = {
  getCompanySettings: () =>
    apiClient.get<CompanySettings>('/company-settings'),

  updateTextSettings: (data: { signatory_name?: string; company_phone?: string }) =>
    apiClient.put<CompanySettings>('/company-settings', data),

  uploadLetterhead: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<CompanySettings>('/company-settings/letterhead', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteLetterhead: () =>
    apiClient.delete<CompanySettings>('/company-settings/letterhead'),

  uploadSignature: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<CompanySettings>('/company-settings/signature', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteSignature: () =>
    apiClient.delete<CompanySettings>('/company-settings/signature'),
};
