import { apiClient } from '@/shared/api/client';
import type {
  BillingAlertResponse,
  InitiatePaymentResponse,
  PaymentHistoryListResponse,
  QuotaStatus,
  SavedCard,
  Subscription,
  VerifyPaymentResponse,
} from '../types';

export const billingApi = {
  getQuota: () => apiClient.get<QuotaStatus>('/billing/quota'),

  initiatePayment: (plan: 'monthly' | 'per_project' | 'card_update', quantity?: number) =>
    apiClient.post<InitiatePaymentResponse>('/billing/payments/initiate', { plan, quantity: quantity ?? 1 }),

  verifyPayment: (moyasar_payment_id: string) =>
    apiClient.post<VerifyPaymentResponse>('/billing/payments/verify', { moyasar_payment_id }),

  listPayments: (params: { page?: number; limit?: number; status?: string; plan?: string } = {}) =>
    apiClient.get<PaymentHistoryListResponse>('/billing/payments', {
      params: {
        page: params.page ?? 1,
        limit: params.limit ?? 10,
        status: params.status || undefined,
        plan: params.plan || undefined,
      },
    }),

  getSubscription: () => apiClient.get<Subscription | null>('/billing/subscription'),

  listCards: () => apiClient.get<SavedCard[]>('/billing/cards'),

  updateCard: (moyasar_payment_id: string) =>
    apiClient.post<{ message: string }>('/billing/cards/update', { moyasar_payment_id }),

  getAlerts: () => apiClient.get<BillingAlertResponse>('/billing/alerts'),
};
