import { apiClient } from '@/shared/api/client';
import type {
  CreateProjectRequest,
  Project,
  ProjectAdmin,
  ProjectAdminListResponse,
  ProjectListResponse,
  UpdateProjectRequest,
} from '../types';

export const projectsApi = {
  list: (params: { page?: number; limit?: number; search?: string; view?: 'all' | 'my' } = {}) =>
    apiClient.get<ProjectListResponse | ProjectAdminListResponse>('/projects', {
      params: {
        page: params.page ?? 1,
        limit: params.limit ?? 10,
        search: params.search || undefined,
        view: params.view || undefined,
      },
    }),

  get: (projectId: string) =>
    apiClient.get<Project | ProjectAdmin>(`/projects/${projectId}`),

  create: (data: CreateProjectRequest) =>
    apiClient.post<Project>('/projects', data),

  update: (projectId: string, data: UpdateProjectRequest) =>
    apiClient.patch<Project>(`/projects/${projectId}`, data),

  getCountries: () => apiClient.get<string[]>('/projects/countries'),
};
