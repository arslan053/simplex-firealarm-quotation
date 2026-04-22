import { useState } from 'react';
import { Calendar } from 'lucide-react';

import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { billingApi } from '../api/billing.api';
import type { Subscription } from '../types';

type ConfirmAction = null | 'renew' | 'cancel';

interface Props {
  subscription: Subscription | null;
  onBuySubscription: () => void;
  onRenewed: () => void;
  hasSavedCard: boolean;
}

export function SubscriptionCard({ subscription, onBuySubscription, onRenewed, hasSavedCard }: Props) {
  const [loading, setLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const isActive = subscription?.status === 'active' && new Date(subscription.expires_at) > new Date();
  const isExpired = subscription ? (!isActive) : false;

  const handleRenewNow = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const { data } = await billingApi.renewNow();
      setSuccess(data.message);
      setConfirmAction(null);
      onRenewed();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Renewal failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const { data } = await billingApi.cancelSubscription();
      setSuccess(data.message);
      setConfirmAction(null);
      onRenewed(); // refetch quota to update UI
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to cancel. Please try again.');
    } finally {
      setLoading(false);
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
          {/* Renew Now — when expired */}
          {isExpired && !confirmAction && (
            hasSavedCard ? (
              <Button size="sm" onClick={() => { setConfirmAction('renew'); setError(''); setSuccess(''); }}>
                Renew Now
              </Button>
            ) : (
              <Button size="sm" onClick={onBuySubscription}>
                Subscribe
              </Button>
            )
          )}
        </div>

        {/* Renew confirmation */}
        {confirmAction === 'renew' && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 space-y-3">
            <p className="text-sm text-indigo-900">
              Your saved card will be charged <strong>250.00 SAR</strong> for a monthly subscription (25 projects, 30 days).
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleRenewNow} isLoading={loading}>
                Confirm & Pay
              </Button>
              <Button size="sm" variant="outline" onClick={() => setConfirmAction(null)} disabled={loading}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Cancel confirmation */}
        {confirmAction === 'cancel' && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
            <p className="text-sm text-red-900">
              Are you sure you want to cancel your subscription? It will remain active until <strong>{expiresAt.toLocaleDateString()}</strong>, but will not renew after that. Your saved card will also be removed.
            </p>
            <div className="flex gap-2">
              <Button size="sm" variant="danger" onClick={handleCancel} isLoading={loading}>
                Yes, Cancel Subscription
              </Button>
              <Button size="sm" variant="outline" onClick={() => setConfirmAction(null)} disabled={loading}>
                Keep Subscription
              </Button>
            </div>
          </div>
        )}

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

        {/* Cancel subscription — shown whenever auto_renew is on */}
        {subscription.auto_renew && !confirmAction && (
          <button
            onClick={() => { setConfirmAction('cancel'); setError(''); setSuccess(''); }}
            className="text-sm text-red-500 hover:text-red-700 transition-colors"
          >
            Cancel Subscription
          </button>
        )}

        {success && (
          <div className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">{success}</div>
        )}
        {error && (
          <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>
        )}
      </div>
    </Card>
  );
}
