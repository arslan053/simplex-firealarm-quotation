import { Calendar, RefreshCw } from 'lucide-react';
import { useState } from 'react';

import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { billingApi } from '../api/billing.api';
import type { Subscription } from '../types';

interface Props {
  subscription: Subscription | null;
  onBuySubscription: () => void;
  onRefresh: () => void;
}

export function SubscriptionCard({ subscription, onBuySubscription, onRefresh }: Props) {
  const [toggling, setToggling] = useState(false);

  const isActive = subscription?.status === 'active' && new Date(subscription.expires_at) > new Date();
  const isExpired = subscription ? (!isActive) : false;

  const handleToggleAutoRenew = async () => {
    if (!subscription) return;
    setToggling(true);
    try {
      await billingApi.toggleAutoRenew(!subscription.auto_renew);
      onRefresh();
    } catch {
      // silently fail
    } finally {
      setToggling(false);
    }
  };

  if (!subscription) {
    return (
      <Card>
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Monthly Subscription</h3>
            <p className="mt-1 text-sm text-gray-500">No active subscription</p>
          </div>
          <Button onClick={onBuySubscription}>Subscribe Now</Button>
        </div>
      </Card>
    );
  }

  const used = subscription.projects_used;
  const limit = subscription.projects_limit;
  const pct = limit > 0 ? Math.round((used / limit) * 100) : 0;
  const expiresAt = new Date(subscription.expires_at);

  return (
    <Card>
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Monthly Subscription</h3>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={isActive ? 'success' : 'danger'}>
                {isActive ? 'Active' : 'Expired'}
              </Badge>
              {isActive && (
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  <Calendar className="h-3 w-3" />
                  Expires {expiresAt.toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
          {isExpired && <Button size="sm" onClick={onBuySubscription}>Renew</Button>}
        </div>

        {/* Progress bar */}
        <div>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-gray-600">{used}/{limit} projects used</span>
            <span className="text-gray-500">{pct}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-200">
            <div
              className={`h-full rounded-full transition-all ${pct >= 100 ? 'bg-red-500' : pct >= 80 ? 'bg-amber-500' : 'bg-indigo-600'}`}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </div>

        {/* Auto-renew toggle */}
        {isActive && (
          <div className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <RefreshCw className="h-4 w-4" />
              Auto-renewal
            </div>
            <button
              onClick={handleToggleAutoRenew}
              disabled={toggling}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                subscription.auto_renew ? 'bg-indigo-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  subscription.auto_renew ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
