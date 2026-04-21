import { useEffect, useState } from 'react';
import { CreditCard, RefreshCw } from 'lucide-react';

import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { billingApi } from '../api/billing.api';
import type { SavedCard } from '../types';

interface Props {
  onChangeCard?: () => void;
}

export function SavedCardsSection({ onChangeCard }: Props) {
  const [cards, setCards] = useState<SavedCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    billingApi.listCards().then(({ data }) => setCards(data)).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Saved Cards</h3>
        {onChangeCard && (
          <Button size="sm" variant="outline" onClick={onChangeCard}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Change Payment Method
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="py-4 text-center text-sm text-gray-500">Loading...</div>
      ) : cards.length === 0 ? (
        <Card>
          <div className="flex items-center gap-3 text-gray-500">
            <CreditCard className="h-5 w-5" />
            <p className="text-sm">No saved cards. A card will be saved on your next payment.</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {cards.map((card) => (
            <Card key={card.id}>
              <div className="flex items-center gap-3">
                <CreditCard className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {card.card_brand ? card.card_brand.toUpperCase() : 'Card'} **** {card.last_four || '????'}
                  </p>
                  {card.expires_month && card.expires_year && (
                    <p className="text-xs text-gray-500">
                      Expires {String(card.expires_month).padStart(2, '0')}/{card.expires_year}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
