import { useState } from 'react';
import { X, FileText, Loader2 } from 'lucide-react';

import { quotationApi } from '../api/quotation.api';
import type { GenerateQuotationRequest, QuotationResponse } from '../types/quotation';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

interface QuotationModalProps {
  projectId: string;
  margin: number;
  existingQuotation: QuotationResponse | null;
  onClose: () => void;
  onGenerated: (quotation: QuotationResponse) => void;
}

const SERVICE_OPTIONS = [
  { value: 1, label: 'Option 1 - Supply Only', description: 'Supply of equipment, warranty, programming, testing & commissioning' },
  { value: 2, label: 'Option 2 - Supply + Installation (no conduiting)', description: 'Supply + engineering, installation, cable pulling, device fixing, programming, T&C' },
  { value: 3, label: 'Option 3 - Supply + Full Installation (with conduiting)', description: 'Supply + engineering, installation, conduiting, cable pulling, device fixing, programming, T&C' },
];

const DEFAULT_PAYMENT_TEXT = `1) 25% Advance with PO.
2) 70% At time of delivery of material.
3) 5% After Testing & Commissioning of Fire Alarm System.`;

function buildDefaultPaymentText(advance: number, delivery: number, completion: number): string {
  const fmt = (v: number) => (v === Math.floor(v) ? String(v) : v.toFixed(1));
  return [
    `1) ${fmt(advance)}% Advance with PO.`,
    `2) ${fmt(delivery)}% At time of delivery of material.`,
    `3) ${fmt(completion)}% After Testing & Commissioning of Fire Alarm System.`,
  ].join('\n');
}

export function QuotationModal({
  projectId,
  margin,
  existingQuotation,
  onClose,
  onGenerated,
}: QuotationModalProps) {
  const [clientName, setClientName] = useState(existingQuotation?.client_name || '');
  const [clientAddress, setClientAddress] = useState(existingQuotation?.client_address || '');
  const [serviceOption, setServiceOption] = useState(existingQuotation?.service_option || 1);
  const [advancePercent, setAdvancePercent] = useState(25);
  const [deliveryPercent, setDeliveryPercent] = useState(70);
  const [completionPercent, setCompletionPercent] = useState(5);

  // If restoring from existing quotation, start in custom mode with stored text
  // Otherwise start in default mode with the standard percentage text
  const hasExistingText = !!existingQuotation?.payment_terms_text;
  const [paymentMode, setPaymentMode] = useState<'default' | 'custom'>(hasExistingText ? 'custom' : 'default');
  const [customPaymentText, setCustomPaymentText] = useState(
    existingQuotation?.payment_terms_text || DEFAULT_PAYMENT_TEXT,
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const percentSum = advancePercent + deliveryPercent + completionPercent;
  const percentValid = Math.abs(percentSum - 100) < 0.01;

  const canSubmit =
    clientName.trim() !== '' &&
    clientAddress.trim() !== '' &&
    (paymentMode === 'custom' ? customPaymentText.trim() !== '' : percentValid) &&
    !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    setError('');

    const payload: GenerateQuotationRequest = {
      client_name: clientName.trim(),
      client_address: clientAddress.trim(),
      service_option: serviceOption,
      margin_percent: margin,
      payment_terms_text: paymentMode === 'custom'
        ? customPaymentText.trim()
        : buildDefaultPaymentText(advancePercent, deliveryPercent, completionPercent),
    };

    try {
      const { data } = await quotationApi.generate(projectId, payload);
      onGenerated(data);
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 mx-4 w-full max-w-lg rounded-xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">
              {existingQuotation ? 'Regenerate Quotation' : 'Generate Quotation'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 hover:bg-gray-100 transition-colors"
          >
            <X className="h-5 w-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* Client Info */}
          <div className="space-y-3">
            <Input
              label="Client Name"
              placeholder="e.g. Ahmed Hassan"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
            />
            <Input
              label="Client Address"
              placeholder="e.g. Riyadh, Saudi Arabia"
              value={clientAddress}
              onChange={(e) => setClientAddress(e.target.value)}
            />
          </div>

          {/* Service Option */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Service Option
            </label>
            <div className="space-y-2">
              {SERVICE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                    serviceOption === opt.value
                      ? 'border-indigo-500 bg-indigo-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="service_option"
                    value={opt.value}
                    checked={serviceOption === opt.value}
                    onChange={() => setServiceOption(opt.value)}
                    className="mt-0.5 h-4 w-4 text-indigo-600"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900">{opt.label}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{opt.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Payment Terms */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Payment Terms
            </label>

            {/* Mode toggle */}
            <div className="mb-3 flex rounded-lg border border-gray-200 p-0.5">
              <button
                type="button"
                onClick={() => setPaymentMode('default')}
                className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  paymentMode === 'default'
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Default
              </button>
              <button
                type="button"
                onClick={() => {
                  if (paymentMode === 'default') {
                    setCustomPaymentText(buildDefaultPaymentText(advancePercent, deliveryPercent, completionPercent));
                  }
                  setPaymentMode('custom');
                }}
                className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  paymentMode === 'custom'
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Custom
              </button>
            </div>

            {paymentMode === 'default' ? (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="mb-1 block text-xs text-gray-500">Advance %</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={advancePercent}
                      onChange={(e) => setAdvancePercent(parseFloat(e.target.value) || 0)}
                      className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-gray-500">Delivery %</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={deliveryPercent}
                      onChange={(e) => setDeliveryPercent(parseFloat(e.target.value) || 0)}
                      className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-gray-500">Completion %</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={completionPercent}
                      onChange={(e) => setCompletionPercent(parseFloat(e.target.value) || 0)}
                      className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                </div>
                {!percentValid && (
                  <p className="mt-1.5 text-xs text-red-600">
                    Percentages must sum to 100 (currently {percentSum.toFixed(1)})
                  </p>
                )}
                {/* Preview */}
                <div className="mt-3 rounded-lg bg-gray-50 p-3">
                  <p className="mb-1 text-xs font-medium text-gray-500">Preview</p>
                  <pre className="whitespace-pre-wrap text-xs text-gray-700 font-sans">
                    {buildDefaultPaymentText(advancePercent, deliveryPercent, completionPercent)}
                  </pre>
                </div>
              </>
            ) : (
              <textarea
                rows={5}
                value={customPaymentText}
                onChange={(e) => setCustomPaymentText(e.target.value)}
                placeholder="Enter custom payment terms..."
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            )}
          </div>

          {/* Margin display */}
          <div className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
            <span className="text-sm text-gray-600">Margin</span>
            <span className="text-sm font-medium text-gray-900">{margin}%</span>
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit} isLoading={loading}>
              {loading ? (
                'Generating...'
              ) : (
                <>
                  <FileText className="mr-2 h-4 w-4" />
                  {existingQuotation ? 'Regenerate' : 'Generate'}
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
