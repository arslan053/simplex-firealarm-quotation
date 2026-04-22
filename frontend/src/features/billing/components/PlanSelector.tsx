import { Check, Minus, Plus } from 'lucide-react';

import { cn } from '@/shared/utils/cn';

interface Props {
  selected: 'monthly' | 'per_project' | null;
  onSelect: (plan: 'monthly' | 'per_project') => void;
  monthlyDisabled?: boolean;
  quantity: number;
  onQuantityChange: (qty: number) => void;
}

export function PlanSelector({ selected, onSelect, monthlyDisabled, quantity, onQuantityChange }: Props) {
  const total = quantity * 25;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Monthly Plan */}
      <button
        onClick={() => !monthlyDisabled && onSelect('monthly')}
        disabled={monthlyDisabled}
        className={cn(
          'relative rounded-xl border-2 p-5 text-left transition-all',
          selected === 'monthly'
            ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600'
            : 'border-gray-200 bg-white hover:border-gray-300',
          monthlyDisabled && 'cursor-not-allowed opacity-50',
        )}
      >
        {selected === 'monthly' && (
          <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600">
            <Check className="h-3 w-3 text-white" />
          </div>
        )}
        <div className="mb-3">
          <p className="font-semibold text-gray-900">Monthly Subscription</p>
          <div className="mt-1">
            <span className="text-2xl font-bold text-gray-900">250 SAR</span>
            <span className="text-sm text-gray-500">/month</span>
          </div>
        </div>
        <ul className="space-y-1.5">
          <li className="flex items-center gap-2 text-sm text-gray-600">
            <Check className="h-3.5 w-3.5 text-green-500" />25 projects included
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-600">
            <Check className="h-3.5 w-3.5 text-green-500" />Valid for 30 days
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-600">
            <Check className="h-3.5 w-3.5 text-green-500" />Auto-renewable
          </li>
        </ul>
        {monthlyDisabled && (
          <p className="mt-2 text-xs text-amber-600">
            Not available — cancel your subscription first to subscribe manually
          </p>
        )}
      </button>

      {/* Per-Project Plan */}
      <button
        onClick={() => onSelect('per_project')}
        className={cn(
          'relative rounded-xl border-2 p-5 text-left transition-all',
          selected === 'per_project'
            ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600'
            : 'border-gray-200 bg-white hover:border-gray-300',
        )}
      >
        {selected === 'per_project' && (
          <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600">
            <Check className="h-3 w-3 text-white" />
          </div>
        )}
        <div className="mb-3">
          <p className="font-semibold text-gray-900">Per-Project</p>
          <div className="mt-1">
            <span className="text-2xl font-bold text-gray-900">{total} SAR</span>
            <span className="text-sm text-gray-500"> for {quantity} credit{quantity > 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* Quantity selector — only when selected */}
        {selected === 'per_project' ? (
          <div
            className="mb-3 space-y-2"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Credits</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); onQuantityChange(Math.max(1, quantity - 1)); }}
                  disabled={quantity <= 1}
                  className="flex h-7 w-7 items-center justify-center rounded border border-gray-300 text-gray-500 hover:bg-white disabled:opacity-40"
                >
                  <Minus className="h-3 w-3" />
                </button>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={quantity}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v) && v >= 1 && v <= 100) onQuantityChange(v);
                  }}
                  className="w-12 rounded border border-gray-300 px-1 py-0.5 text-center text-sm font-medium focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                <button
                  onClick={(e) => { e.stopPropagation(); onQuantityChange(Math.min(100, quantity + 1)); }}
                  disabled={quantity >= 100}
                  className="flex h-7 w-7 items-center justify-center rounded border border-gray-300 text-gray-500 hover:bg-white disabled:opacity-40"
                >
                  <Plus className="h-3 w-3" />
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">25 SAR x {quantity}</span>
              <span className="font-semibold text-gray-900">{total}.00 SAR</span>
            </div>
          </div>
        ) : (
          <ul className="space-y-1.5">
            <li className="flex items-center gap-2 text-sm text-gray-600">
              <Check className="h-3.5 w-3.5 text-green-500" />25 SAR per credit
            </li>
            <li className="flex items-center gap-2 text-sm text-gray-600">
              <Check className="h-3.5 w-3.5 text-green-500" />Never expires
            </li>
            <li className="flex items-center gap-2 text-sm text-gray-600">
              <Check className="h-3.5 w-3.5 text-green-500" />Use anytime
            </li>
          </ul>
        )}
      </button>
    </div>
  );
}
