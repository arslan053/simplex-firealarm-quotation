import { useState } from 'react';
import { CreditCard } from 'lucide-react';

import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { billingApi } from '../api/billing.api';
import { useQuota } from '../hooks/useQuota';
import { SubscriptionCard } from '../components/SubscriptionCard';
import { CreditBalanceCard } from '../components/CreditBalanceCard';
import { PlanSelector } from '../components/PlanSelector';
import { MoyasarPaymentForm } from '../components/MoyasarPaymentForm';
import { PaymentHistoryTable } from '../components/PaymentHistoryTable';
import { SavedCardsSection } from '../components/SavedCardsSection';
import type { InitiatePaymentResponse } from '../types';

type FlowMode = 'idle' | 'select_plan' | 'payment' | 'update_card';

export function BillingPage() {
  const { user } = useAuth();
  const { subscription, creditsBalance } = useQuota();

  const [flowMode, setFlowMode] = useState<FlowMode>('idle');
  const [selectedPlan, setSelectedPlan] = useState<'monthly' | 'per_project' | null>(null);
  const [creditQuantity, setCreditQuantity] = useState(1);
  const [paymentData, setPaymentData] = useState<InitiatePaymentResponse | null>(null);
  const [initiating, setInitiating] = useState(false);
  const [error, setError] = useState('');

  const hasActiveSub = subscription?.status === 'active' && new Date(subscription.expires_at) > new Date();

  const handleSelectPlan = (plan: 'monthly' | 'per_project') => {
    setSelectedPlan(plan);
    setPaymentData(null);
    setError('');
    setFlowMode('select_plan');
  };

  const handleInitiatePayment = async () => {
    if (!selectedPlan) return;
    setInitiating(true);
    setError('');
    try {
      const qty = selectedPlan === 'per_project' ? creditQuantity : 1;
      const { data } = await billingApi.initiatePayment(selectedPlan, qty);
      setPaymentData(data);
      setFlowMode('payment');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to initiate payment');
    } finally {
      setInitiating(false);
    }
  };

  const handleCancel = () => {
    setFlowMode('idle');
    setSelectedPlan(null);
    setPaymentData(null);
    setError('');
  };

  const handleChangeCard = () => {
    setFlowMode('update_card');
    setError('');
  };

  const callbackUrl = `${window.location.origin}/billing/verify`;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
          <CreditCard className="h-5 w-5 text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
          <p className="text-sm text-gray-500">Manage your subscription and project credits</p>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        <SubscriptionCard
          subscription={subscription}
          onBuySubscription={() => handleSelectPlan('monthly')}
        />
        <CreditBalanceCard
          balance={creditsBalance}
          onBuyCredits={() => handleSelectPlan('per_project')}
        />
      </div>

      {/* Plan Selection */}
      {flowMode === 'select_plan' && !paymentData && (
        <Card>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Choose a Plan</h3>
              <Button size="sm" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
            </div>
            <PlanSelector
              selected={selectedPlan}
              onSelect={(plan) => { setSelectedPlan(plan); }}
              monthlyDisabled={hasActiveSub}
              quantity={creditQuantity}
              onQuantityChange={setCreditQuantity}
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button onClick={handleInitiatePayment} isLoading={initiating}>
              Proceed to Payment
            </Button>
          </div>
        </Card>
      )}

      {/* Moyasar Payment Form */}
      {flowMode === 'payment' && paymentData && (
        <Card>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Complete Payment — {paymentData.description}
              </h3>
              <Button size="sm" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
            </div>
            <MoyasarPaymentForm
              amount={paymentData.amount}
              currency={paymentData.currency}
              description={paymentData.description}
              callbackUrl={callbackUrl}
              metadata={{
                internal_id: paymentData.internal_id,
                tenant_id: user?.tenant_id || '',
                plan: selectedPlan || '',
              }}
            />
          </div>
        </Card>
      )}

      {/* Card Update — $1 verification charge, automatically refunded */}
      {flowMode === 'update_card' && (
        <Card>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Change Payment Method</h3>
              <Button size="sm" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
            </div>

            <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 space-y-1">
              <p className="font-medium">How it works:</p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>A <strong>$1.00 verification charge</strong> will be placed on your new card.</li>
                <li>This charge is <strong>automatically refunded</strong> once your card is verified.</li>
                <li>Your new card will replace the current one and be used for future auto-renewals.</li>
                <li>If the refund doesn't appear within a few business days, please contact support.</li>
              </ul>
            </div>

            {!paymentData ? (
              <Button
                onClick={async () => {
                  setInitiating(true);
                  try {
                    const { data } = await billingApi.initiatePayment('card_update');
                    setPaymentData(data);
                  } catch (err: any) {
                    setError(err?.response?.data?.detail || 'Failed to start card update');
                  } finally {
                    setInitiating(false);
                  }
                }}
                isLoading={initiating}
              >
                Enter New Card Details
              </Button>
            ) : (
              <MoyasarPaymentForm
                amount={paymentData.amount}
                currency={paymentData.currency}
                description={paymentData.description}
                callbackUrl={callbackUrl}
                metadata={{
                  internal_id: paymentData.internal_id,
                  tenant_id: user?.tenant_id || '',
                  plan: 'card_update',
                }}
              />
            )}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        </Card>
      )}

      {/* Saved Cards */}
      <Card>
        <SavedCardsSection onChangeCard={handleChangeCard} />
      </Card>

      {/* Payment History */}
      <Card>
        <PaymentHistoryTable />
      </Card>
    </div>
  );
}
