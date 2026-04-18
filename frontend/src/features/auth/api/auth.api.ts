import { apiClient } from '@/shared/api/client';
import type {
  ChangePasswordRequest,
  ForgotPasswordRequest,
  LoginRequest,
  LoginResponse,
  MessageResponse,
  ResetPasswordRequest,
  UpdateProfileRequest,
  User,
} from '../types';

export const authApi = {
  login: (data: LoginRequest) => apiClient.post<LoginResponse>('/auth/login', data),

  me: () => apiClient.get<User>('/auth/me'),

  changePassword: (data: ChangePasswordRequest) =>
    apiClient.post<MessageResponse>('/auth/change-password', data),

  forgotPassword: (data: ForgotPasswordRequest) =>
    apiClient.post<MessageResponse>('/auth/forgot-password', data),

  resetPassword: (data: ResetPasswordRequest) =>
    apiClient.post<MessageResponse>('/auth/reset-password', data),

  updateProfile: (data: UpdateProfileRequest) =>
    apiClient.patch<User>('/auth/profile', data),
};
