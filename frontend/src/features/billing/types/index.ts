export interface Subscription {
  id: string;
  status: 'active' | 'expired';
  projects_used: number;
  projects_limit: number;
  starts_at: string;
  expires_at: string;
  auto_renew: boolean;
  amount_paid: number;
  renewal_attempts?: number;
}

export interface QuotaStatus {
  can_create: boolean;
  source: 'subscription' | 'credits' | null;
  message: string;
  subscription: Subscription | null;
  credits_balance: number;
  can_buy_monthly: boolean;
}

export interface InitiatePaymentResponse {
  internal_id: string;
  amount: number;
  currency: string;
  given_id: string;
  description: string;
}

export interface VerifyPaymentResponse {
  success: boolean;
  message: string;
  quota: QuotaStatus | null;
}

export interface PaymentHistory {
  id: string;
  plan: 'monthly' | 'per_project';
  amount: number;
  currency: string;
  status: 'pending' | 'paid' | 'failed';
  payment_type: 'manual' | 'auto_renewal';
  moyasar_payment_id: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface PaymentHistoryListResponse {
  data: PaymentHistory[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

export interface SavedCard {
  id: string;
  card_brand: string | null;
  last_four: string | null;
  expires_month: number | null;
  expires_year: number | null;
  created_at: string;
}

export interface BillingAlert {
  type: string;
  message: string;
}

export interface BillingAlertResponse {
  alerts: BillingAlert[];
}
