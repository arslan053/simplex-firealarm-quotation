import { useCallback, useEffect, useState } from 'react';
import { Calculator, Loader2, AlertCircle, Download, FileText, RefreshCw, Eye } from 'lucide-react';

import { pricingApi } from '../api/pricing.api';
import { quotationApi } from '../api/quotation.api';
import { panelSelectionApi } from '../api/panel-selection.api';
import type { PricingItem, PricingResponse } from '../types/pricing';
import type { QuotationResponse } from '../types/quotation';
import { QuotationModal } from './QuotationModal';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

function formatSAR(value: number): string {
  return `SAR ${value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatQty(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2).replace(/\.?0+$/, '');
}

function roundTwo(value: number): number {
  return Math.round(value * 100) / 100;
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

interface PricingSectionProps {
  projectId: string;
  projectName: string;
}

export function PricingSection({ projectId, projectName }: PricingSectionProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [pricing, setPricing] = useState<PricingResponse | null>(null);
  const [margin, setMargin] = useState(0);
  const [panelReady, setPanelReady] = useState(false);
  const [checkingPanel, setCheckingPanel] = useState(true);
  const [showQuotationModal, setShowQuotationModal] = useState(false);
  const [quotation, setQuotation] = useState<QuotationResponse | null>(null);
  const [downloading, setDownloading] = useState(false);

  // Check if panel selection is completed
  useEffect(() => {
    setCheckingPanel(true);
    panelSelectionApi
      .getResults(projectId)
      .then(({ data }) => {
        setPanelReady(data.panel_supported && data.status !== 'empty');
      })
      .catch(() => setPanelReady(false))
      .finally(() => setCheckingPanel(false));
  }, [projectId]);

  const fetchPricing = useCallback(async () => {
    try {
      const { data } = await pricingApi.get(projectId);
      setPricing(data);
    } catch {
      // No pricing yet
    }
  }, [projectId]);

  useEffect(() => {
    fetchPricing();
  }, [fetchPricing]);

  // Fetch existing quotation
  useEffect(() => {
    quotationApi
      .get(projectId)
      .then(({ data }) => setQuotation(data))
      .catch(() => {});
  }, [projectId]);

  const openQuotationInNewTab = async () => {
    try {
      const { data } = await quotationApi.preview(projectId);
      const url = URL.createObjectURL(data);
      window.open(url, '_blank');
    } catch {
      // ignore
    }
  };

  const handleDownloadQuotation = async () => {
    setDownloading(true);
    try {
      const { data } = await quotationApi.download(projectId);
      // Force download via hidden anchor
      const a = document.createElement('a');
      a.href = data.url;
      a.download = data.file_name;
      a.click();
    } catch {
      // ignore
    } finally {
      setDownloading(false);
    }
  };

  const handleCalculate = async () => {
    if (pricing) {
      const confirmed = window.confirm(
        'This will recalculate all pricing. Continue?',
      );
      if (!confirmed) return;
    }

    setLoading(true);
    setError('');
    try {
      const { data } = await pricingApi.calculate(projectId);
      setPricing(data);
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setLoading(false);
    }
  };

  const deviceItems = pricing?.items.filter((i) => i.section === 'device') ?? [];
  const panelItems = pricing?.items.filter((i) => i.section === 'panel') ?? [];

  const calcWithMargin = (totalSar: number) => {
    const marginAmount = roundTwo(totalSar * (margin / 100));
    return roundTwo(totalSar + marginAmount);
  };

  const allWithMargin = pricing
    ? pricing.items.reduce((sum, i) => sum + calcWithMargin(i.total_sar), 0)
    : 0;
  const subtotal = roundTwo(allWithMargin);
  const vatAmount = roundTwo(subtotal * 0.15);
  const grandTotal = roundTwo(subtotal + vatAmount);

  const canCalculate = panelReady && !loading && !checkingPanel;

  const handleDownload = () => {
    if (!pricing) return;

    const header = [
      '#',
      'Description',
      'Products',
      'Qty',
      'Unit Cost (SAR)',
      'Total (SAR)',
      `${margin}% Margin (SAR)`,
    ];
    const rows: string[] = [header.join(',')];

    const addSection = (label: string, items: PricingItem[]) => {
      if (items.length === 0) return;
      rows.push('');
      rows.push(csvEscape(label));
      for (const item of items) {
        const codes = item.product_details.map((d) => d.code).join(' | ');
        rows.push(
          [
            String(item.row_number),
            csvEscape(item.description || ''),
            csvEscape(codes),
            formatQty(item.quantity),
            item.unit_cost_sar.toFixed(2),
            item.total_sar.toFixed(2),
            calcWithMargin(item.total_sar).toFixed(2),
          ].join(','),
        );
      }
    };

    addSection('DEVICE SELECTION', deviceItems);
    addSection('PANEL CONFIGURATION', panelItems);

    rows.push('');
    rows.push(`,,,,,,`);
    rows.push(`,,,,,Subtotal,${subtotal.toFixed(2)}`);
    rows.push(`,,,,,VAT (15%),${vatAmount.toFixed(2)}`);
    rows.push(`,,,,,Grand Total,${grandTotal.toFixed(2)}`);

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pricing-${projectName || 'quotation'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Quotation Pricing</h2>
          <p className="text-sm text-gray-500">
            Calculate project quotation with margin and VAT
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pricing && (
            <>
              <Button variant="outline" size="sm" onClick={handleDownload}>
                <Download className="mr-1.5 h-4 w-4" />
                CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowQuotationModal(true)}
              >
                <FileText className="mr-1.5 h-4 w-4" />
                {quotation ? 'Regenerate Quotation' : 'Generate Quotation'}
              </Button>
            </>
          )}
          <Button
            variant="primary"
            onClick={handleCalculate}
            disabled={!canCalculate}
            isLoading={loading}
          >
            <Calculator className="mr-2 h-4 w-4" />
            {loading ? 'Calculating...' : 'Calculate Pricing'}
          </Button>
        </div>
      </div>

      {/* Quotation Card — shown at top when quotation exists */}
      {quotation && pricing && !loading && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 px-6 py-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
                <FileText className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  {quotation.original_file_name}
                </h3>
                <p className="text-xs text-gray-500">
                  Ref: {quotation.reference_number} &middot; Option {quotation.service_option} &middot; Margin {quotation.margin_percent}% &middot;{' '}
                  {new Date(quotation.updated_at).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowQuotationModal(true)}
              >
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                Regenerate
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={openQuotationInNewTab}
              >
                <Eye className="mr-1.5 h-3.5 w-3.5" />
                Show
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleDownloadQuotation}
                isLoading={downloading}
              >
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Download
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Panel not ready warning */}
      {!checkingPanel && !panelReady && !pricing && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>
            Panel analysis and configuration must be completed before pricing
            can be calculated.
          </span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <Card>
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-indigo-600">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Calculating pricing...</span>
          </div>
        </Card>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Pricing Display */}
      {pricing && !loading && (
        <>
          {/* Letterhead */}
          <div className="rounded-lg border border-gray-200 bg-white px-6 py-8 text-center shadow-sm">
            <h3 className="text-2xl font-bold tracking-tight text-gray-900">
              Rawabi &amp; Gulf Marvel
            </h3>
            <p className="mt-3 text-base font-medium text-gray-700">
              {projectName}
            </p>
            <p className="mt-1 text-sm text-gray-400">
              {new Date(pricing.calculated_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>

          {/* Margin Input */}
          <div className="rounded-lg border border-gray-200 bg-white px-6 py-4 shadow-sm">
            <div className="flex items-center gap-4">
              <label
                htmlFor="margin-input"
                className="text-sm font-medium text-gray-700 whitespace-nowrap"
              >
                Margin %
              </label>
              <input
                id="margin-input"
                type="number"
                min="0"
                step="0.1"
                value={margin}
                onChange={(e) => setMargin(parseFloat(e.target.value) || 0)}
                className="w-28 rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              {margin > 0 && (
                <span className="text-xs text-gray-400">
                  Applied to all line items
                </span>
              )}
            </div>
          </div>

          {/* Section 1: Device Selection */}
          {deviceItems.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-gray-200 bg-gray-50 px-6 py-3">
                <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
                  Device Selection
                </h4>
              </div>
              <PricingTable
                items={deviceItems}
                margin={margin}
                calcWithMargin={calcWithMargin}
              />
            </div>
          )}

          {/* Section 2: Panel Configuration */}
          {panelItems.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-gray-200 bg-gray-50 px-6 py-3">
                <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
                  Panel Configuration
                </h4>
              </div>
              <PricingTable
                items={panelItems}
                margin={margin}
                calcWithMargin={calcWithMargin}
              />
            </div>
          )}

          {/* Totals */}
          <div className="rounded-lg border border-gray-200 bg-white px-6 py-5 shadow-sm">
            <div className="flex flex-col items-end space-y-3">
              <div className="grid grid-cols-2 gap-x-6 text-sm">
                <span className="text-right text-gray-500">Subtotal:</span>
                <span className="text-right font-medium text-gray-900">
                  {formatSAR(subtotal)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-6 text-sm">
                <span className="text-right text-gray-500">VAT (15%):</span>
                <span className="text-right font-medium text-gray-900">
                  {formatSAR(vatAmount)}
                </span>
              </div>
              <div className="border-t border-gray-200 pt-3 grid grid-cols-2 gap-x-6">
                <span className="text-right font-semibold text-gray-900">
                  Grand Total:
                </span>
                <span className="text-right text-lg font-bold text-indigo-700">
                  {formatSAR(grandTotal)}
                </span>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Quotation Modal */}
      {showQuotationModal && (
        <QuotationModal
          projectId={projectId}
          margin={margin}
          existingQuotation={quotation}
          onClose={() => setShowQuotationModal(false)}
          onGenerated={(q) => {
            setQuotation(q);
            setShowQuotationModal(false);
            // Auto-open the generated quotation as PDF in a new tab
            quotationApi.preview(projectId).then(({ data }) => {
              const url = URL.createObjectURL(data);
              window.open(url, '_blank');
            }).catch(() => {});
          }}
        />
      )}

      {/* Empty state */}
      {!loading && !pricing && !error && panelReady && (
        <Card>
          <div className="flex flex-col items-center py-14 text-center">
            <Calculator className="mb-4 h-12 w-12 text-gray-300" />
            <h3 className="text-lg font-semibold text-gray-900">
              No pricing calculated yet
            </h3>
            <p className="mt-2 max-w-md text-sm text-gray-500">
              Click &quot;Calculate Pricing&quot; to generate a quotation
              breakdown with device and panel pricing.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

function PricingTable({
  items,
  margin,
  calcWithMargin,
}: {
  items: PricingItem[];
  margin: number;
  calcWithMargin: (totalSar: number) => number;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50/50 text-xs font-medium uppercase tracking-wider text-gray-500">
            <th className="py-3 pl-6 pr-2 w-10">#</th>
            <th className="px-3 py-3">Description</th>
            <th className="px-3 py-3 text-center w-14">Qty</th>
            <th className="px-3 py-3 text-right w-32">Unit Cost</th>
            <th className="px-3 py-3 text-right w-32">Total</th>
            <th className="px-3 py-3 text-right w-36">
              {margin}% Margin
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {items.map((item) => {
            const codes = item.product_details.map((d) => d.code).join(', ');
            return (
              <tr key={item.id} className="hover:bg-gray-50/60 transition-colors">
                <td className="py-3.5 pl-6 pr-2 text-gray-400 tabular-nums">
                  {item.row_number}
                </td>
                <td className="px-3 py-3.5">
                  <div className="text-gray-800">
                    {item.description || '\u2014'}
                  </div>
                  {codes && (
                    <div className="mt-1 text-xs text-gray-400 font-mono">
                      {codes}
                    </div>
                  )}
                </td>
                <td className="px-3 py-3.5 text-center tabular-nums text-gray-900">
                  {formatQty(item.quantity)}
                </td>
                <td className="px-3 py-3.5 text-right tabular-nums text-gray-900">
                  {formatSAR(item.unit_cost_sar)}
                </td>
                <td className="px-3 py-3.5 text-right tabular-nums text-gray-900">
                  {formatSAR(item.total_sar)}
                </td>
                <td className="px-3 py-3.5 text-right tabular-nums font-medium text-gray-900">
                  {formatSAR(calcWithMargin(item.total_sar))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
