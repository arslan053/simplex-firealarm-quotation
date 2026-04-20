import { Coins } from 'lucide-react';

import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';

interface Props {
  balance: number;
  onBuyCredits: () => void;
}

export function CreditBalanceCard({ balance, onBuyCredits }: Props) {
  return (
    <Card>
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Project Credits</h3>
            <p className="mt-1 text-sm text-gray-500">$25 per credit (never expire)</p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50">
            <Coins className="h-5 w-5 text-indigo-600" />
          </div>
        </div>

        <div className="text-3xl font-bold text-gray-900">
          {balance}
          <span className="ml-2 text-base font-normal text-gray-500">
            credit{balance !== 1 ? 's' : ''} remaining
          </span>
        </div>

        <Button variant="outline" onClick={onBuyCredits}>
          Buy Project Credits
        </Button>
      </div>
    </Card>
  );
}
