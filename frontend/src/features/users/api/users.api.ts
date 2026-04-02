import { apiClient } from '@/shared/api/client';
import type { InviteUserRequest, TenantUser, UpdateRoleRequest, UserListResponse } from '../types';

export const usersApi = {
  list: (skip = 0, limit = 50) =>
    apiClient.get<UserListResponse>('/tenant/users', { params: { skip, limit } }),

  invite: (data: InviteUserRequest) =>
    apiClient.post<TenantUser>('/tenant/users/invite', data),

  updateRole: (userId: string, data: UpdateRoleRequest) =>
    apiClient.patch<TenantUser>(`/tenant/users/${userId}`, data),

  deactivate: (userId: string) =>
    apiClient.post<TenantUser>(`/tenant/users/${userId}/deactivate`),
};
