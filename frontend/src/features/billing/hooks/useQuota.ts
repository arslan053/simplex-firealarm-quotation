import { useCallback, useEffect, useState } from 'react';

import { billingApi } from '../api/billing.api';
import type { QuotaStatus } from '../types';

export function useQuota() {
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await billingApi.getQuota();
      setQuota(data);
      setError(null);
    } catch {
      setError('Failed to load quota');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return {
    canCreate: quota?.can_create ?? false,
    source: quota?.source ?? null,
    message: quota?.message ?? '',
    subscription: quota?.subscription ?? null,
    creditsBalance: quota?.credits_balance ?? 0,
    canBuyMonthly: quota?.can_buy_monthly ?? false,
    isLoading,
    error,
    refetch: fetch,
  };
}
