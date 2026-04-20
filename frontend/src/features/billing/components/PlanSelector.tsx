import { Check } from 'lucide-react';

import { cn } from '@/shared/utils/cn';

interface Props {
  selected: 'monthly' | 'per_project' | null;
  onSelect: (plan: 'monthly' | 'per_project') => void;
  monthlyDisabled?: boolean;
}

const plans = [
  {
    id: 'monthly' as const,
    name: 'Monthly Subscription',
    price: '$250',
    period: '/month',
    features: ['25 projects included', 'Valid for 30 days', 'Auto-renewable'],
  },
  {
    id: 'per_project' as const,
    name: 'Per-Project',
    price: '$25',
    period: '/project',
    features: ['1 project credit', 'Never expires', 'Use anytime'],
  },
];

export function PlanSelector({ selected, onSelect, monthlyDisabled }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {plans.map((plan) => {
        const isSelected = selected === plan.id;
        const isDisabled = plan.id === 'monthly' && monthlyDisabled;

        return (
          <button
            key={plan.id}
            onClick={() => !isDisabled && onSelect(plan.id)}
            disabled={isDisabled}
            className={cn(
              'relative rounded-xl border-2 p-5 text-left transition-all',
              isSelected
                ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600'
                : 'border-gray-200 bg-white hover:border-gray-300',
              isDisabled && 'cursor-not-allowed opacity-50',
            )}
          >
            {isSelected && (
              <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600">
                <Check className="h-3 w-3 text-white" />
              </div>
            )}

            <div className="mb-3">
              <p className="font-semibold text-gray-900">{plan.name}</p>
              <div className="mt-1">
                <span className="text-2xl font-bold text-gray-900">{plan.price}</span>
                <span className="text-sm text-gray-500">{plan.period}</span>
              </div>
            </div>

            <ul className="space-y-1.5">
              {plan.features.map((f) => (
                <li key={f} className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-3.5 w-3.5 text-green-500" />
                  {f}
                </li>
              ))}
            </ul>

            {isDisabled && (
              <p className="mt-2 text-xs text-amber-600">
                Active subscription exists — wait until it expires
              </p>
            )}
          </button>
        );
      })}
    </div>
  );
}
