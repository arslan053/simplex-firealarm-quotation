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
  const { subscription, creditsBalance, refetch } = useQuota();

  const [flowMode, setFlowMode] = useState<FlowMode>('idle');
  const [selectedPlan, setSelectedPlan] = useState<'monthly' | 'per_project' | null>(null);
  const [paymentData, setPaymentData] = useState<InitiatePaymentResponse | null>(null);
  const [initiating, setInitiating] = useState(false);
  const [error, setError] = useState('');
  const [cardUpdateResult, setCardUpdateResult] = useState<string | null>(null);

  const hasActiveSub = subscription?.status === 'active' && new Date(subscription.expires_at) > new Date();
  const renewalPending = (subscription?.renewal_attempts ?? 0) > 0 && subscription?.auto_renew;

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
      const { data } = await billingApi.initiatePayment(selectedPlan);
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
    setCardUpdateResult(null);
  };

  const handleChangeCard = () => {
    // For card update, we initiate a small payment with save_card
    // The Moyasar form will handle the tokenization
    setFlowMode('update_card');
    setError('');
    setCardUpdateResult(null);
    // Initiate a per_project payment to get a real token via save_card
    // The card gets saved during the verify step
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
          onRefresh={refetch}
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

      {/* Card Update Form */}
      {flowMode === 'update_card' && (
        <Card>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Update Payment Method</h3>
              <Button size="sm" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
            </div>
            <p className="text-sm text-gray-600">
              Enter your new card details below. A small verification charge may be applied and refunded.
              {renewalPending && ' Your subscription will be automatically renewed with the new card.'}
            </p>
            {/* Use a per_project payment as the vehicle to save a new card */}
            {!paymentData ? (
              <Button
                onClick={async () => {
                  setInitiating(true);
                  try {
                    const { data } = await billingApi.initiatePayment('per_project');
                    setPaymentData(data);
                  } catch (err: any) {
                    setError(err?.response?.data?.detail || 'Failed to start card update');
                  } finally {
                    setInitiating(false);
                  }
                }}
                isLoading={initiating}
              >
                Continue to Card Entry
              </Button>
            ) : (
              <MoyasarPaymentForm
                amount={paymentData.amount}
                currency={paymentData.currency}
                description="Card update — 1 project credit"
                callbackUrl={callbackUrl}
                metadata={{
                  internal_id: paymentData.internal_id,
                  tenant_id: user?.tenant_id || '',
                  plan: 'per_project',
                }}
              />
            )}
            {error && <p className="text-sm text-red-600">{error}</p>}
            {cardUpdateResult && (
              <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
                {cardUpdateResult}
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Saved Cards */}
      <Card>
        <SavedCardsSection
          onChangeCard={handleChangeCard}
          renewalPending={renewalPending}
        />
      </Card>

      {/* Payment History */}
      <Card>
        <PaymentHistoryTable />
      </Card>
    </div>
  );
}
