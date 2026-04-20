import { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

import { useAuth } from '@/features/auth/hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { billingApi } from '../api/billing.api';
import type { BillingAlert as BillingAlertType } from '../types';

export function BillingAlert() {
  const { user } = useAuth();
  const { isAdminDomain } = useTenant();
  const [alerts, setAlerts] = useState<BillingAlertType[]>([]);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Only show to admins on tenant domain
    if (isAdminDomain || user?.role !== 'admin') return;

    billingApi.getAlerts().then(({ data }) => {
      setAlerts(data.alerts);
    }).catch(() => {});
  }, [user, isAdminDomain]);

  if (dismissed || alerts.length === 0) return null;

  return (
    <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
        <div className="flex-1">
          {alerts.map((alert, i) => (
            <p key={i} className="text-sm text-amber-800">{alert.message}</p>
          ))}
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="flex-shrink-0 text-amber-400 hover:text-amber-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
