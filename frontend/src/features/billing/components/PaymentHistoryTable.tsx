import { useEffect, useState } from 'react';

import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { billingApi } from '../api/billing.api';
import type { PaymentHistory } from '../types';

export function PaymentHistoryTable() {
  const [payments, setPayments] = useState<PaymentHistory[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  const fetch = async () => {
    setIsLoading(true);
    try {
      const { data } = await billingApi.listPayments({
        page,
        limit: 10,
        status: statusFilter || undefined,
      });
      setPayments(data.data);
      setTotalPages(data.pagination.total_pages);
    } catch {
      // silently fail
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, [page, statusFilter]);

  const statusVariant = (s: string) => {
    switch (s) {
      case 'paid': return 'success' as const;
      case 'failed': return 'danger' as const;
      default: return 'warning' as const;
    }
  };

  const formatAmount = (amount: number, currency: string) => {
    const value = amount / 100;
    return `${value.toFixed(2)} ${currency}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Payment History</h3>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">All</option>
          <option value="paid">Paid</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-sm text-gray-500">Loading...</div>
      ) : payments.length === 0 ? (
        <div className="py-8 text-center text-sm text-gray-500">No payment history yet.</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-gray-500">
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium">Plan</th>
                  <th className="pb-2 font-medium">Amount</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-b last:border-0">
                    <td className="py-3 text-gray-700">
                      {new Date(p.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 text-gray-700">
                      {p.plan === 'monthly' ? 'Monthly' : 'Per-Project'}
                    </td>
                    <td className="py-3 text-gray-700">{formatAmount(p.amount, p.currency)}</td>
                    <td className="py-3 text-gray-500">
                      {p.payment_type === 'auto_renewal' ? 'Auto' : 'Manual'}
                    </td>
                    <td className="py-3">
                      <Badge variant={statusVariant(p.status)}>{p.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <span className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
