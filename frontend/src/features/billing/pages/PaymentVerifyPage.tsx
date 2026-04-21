import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { billingApi } from '../api/billing.api';
import type { VerifyPaymentResponse } from '../types';

export function PaymentVerifyPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<VerifyPaymentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const verifiedRef = useRef(false);

  useEffect(() => {
    // Prevent double call in React 18 StrictMode
    if (verifiedRef.current) return;
    verifiedRef.current = true;

    const moyasarId = searchParams.get('id');
    if (!moyasarId) {
      setError('Missing payment ID in URL.');
      setIsLoading(false);
      return;
    }

    billingApi
      .verifyPayment(moyasarId)
      .then(({ data }) => {
        setResult(data);
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Payment verification failed.');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [searchParams]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-md py-20">
        <Card>
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
            <p className="text-gray-600">Verifying your payment...</p>
          </div>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-md py-20">
        <Card>
          <div className="flex flex-col items-center gap-4 py-8">
            <XCircle className="h-12 w-12 text-red-500" />
            <h2 className="text-lg font-semibold text-gray-900">Payment Failed</h2>
            <p className="text-center text-sm text-gray-600">{error}</p>
            <Button onClick={() => navigate('/billing')}>Back to Billing</Button>
          </div>
        </Card>
      </div>
    );
  }

  if (result?.success) {
    return (
      <div className="mx-auto max-w-md py-20">
        <Card>
          <div className="flex flex-col items-center gap-4 py-8">
            <CheckCircle className="h-12 w-12 text-green-500" />
            <h2 className="text-lg font-semibold text-gray-900">Payment Successful</h2>
            <p className="text-center text-sm text-gray-600">{result.message}</p>
            {result.quota && (
              <div className="mt-2 w-full rounded-lg bg-green-50 px-4 py-3 text-center text-sm text-green-800">
                {result.quota.can_create
                  ? result.quota.message
                  : 'Your billing has been updated.'}
              </div>
            )}
            <Button onClick={() => navigate('/billing')}>Back to Billing</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md py-20">
      <Card>
        <div className="flex flex-col items-center gap-4 py-8">
          <XCircle className="h-12 w-12 text-red-500" />
          <h2 className="text-lg font-semibold text-gray-900">Payment Not Completed</h2>
          <p className="text-center text-sm text-gray-600">
            {result?.message || 'Something went wrong.'}
          </p>
          <Button onClick={() => navigate('/billing')}>Back to Billing</Button>
        </div>
      </Card>
    </div>
  );
}
