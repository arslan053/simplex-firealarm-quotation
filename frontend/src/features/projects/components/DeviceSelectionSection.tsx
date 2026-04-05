import { useCallback, useEffect, useRef, useState } from 'react';
import { Cpu, Loader2, AlertCircle, CheckCircle, ChevronLeft, ChevronRight, Download, RefreshCw } from 'lucide-react';

import { deviceSelectionApi } from '../api/device-selection.api';
import type { DeviceSelectionJobStatus, DeviceSelectionItem, PaginationMeta } from '../types/device-selection';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

const POLL_INTERVAL = 3000;
const PAGE_SIZE = 20;

interface DeviceSelectionSectionProps {
  projectId: string;
  projectName?: string;
  refreshKey?: number;
  hasSpec?: boolean;
}

export function DeviceSelectionSection({ projectId, projectName = '', refreshKey = 0, hasSpec = true }: DeviceSelectionSectionProps) {
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<DeviceSelectionJobStatus | null>(null);
  const [error, setError] = useState('');
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [results, setResults] = useState<DeviceSelectionItem[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [expandedReasons, setExpandedReasons] = useState<Set<string>>(new Set());
  const [networkType, setNetworkType] = useState<string | null>(null);
  const [networkTypeAuto, setNetworkTypeAuto] = useState<string | null>(null);
  const [networkSaving, setNetworkSaving] = useState(false);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const toggleReason = useCallback((id: string) => {
    setExpandedReasons((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const fetchResults = useCallback(
    async (page: number) => {
      setResultsLoading(true);
      try {
        const { data } = await deviceSelectionApi.getResults(projectId, { page, limit: PAGE_SIZE });
        setResults(data.data);
        setPagination(data.pagination);
        setCurrentPage(page);
        setExpandedReasons(new Set());
        setNetworkType(data.network_type);
        setNetworkTypeAuto(data.network_type_auto);
      } catch (err) {
        setError(normalizeError(err).message);
      } finally {
        setResultsLoading(false);
      }
    },
    [projectId],
  );

  const pollStatus = useCallback(
    async (jid: string) => {
      try {
        const { data } = await deviceSelectionApi.getStatus(projectId, jid);
        setJobStatus(data);

        if (data.status === 'success') {
          stopPolling();
          setLoading(false);
          fetchResults(1);
        } else if (data.status === 'failed') {
          stopPolling();
          setLoading(false);
          setError(data.message);
        }
      } catch (err) {
        stopPolling();
        setLoading(false);
        setError(normalizeError(err).message);
      }
    },
    [projectId, stopPolling, fetchResults],
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // Load existing results on mount (and re-fetch when refreshKey changes)
  useEffect(() => {
    fetchResults(1);
  }, [fetchResults, refreshKey]);

  // Check for active job on mount (resume polling if user navigated away)
  useEffect(() => {
    deviceSelectionApi.getActiveJob(projectId).then(({ data }) => {
      if (data.active && data.job_id) {
        setLoading(true);
        setJobStatus({
          job_id: data.job_id,
          status: data.status as 'running',
          message: data.message || 'Matching BOQ items to devices...',
          matched_count: 0,
        });
        pollingRef.current = setInterval(() => {
          pollStatus(data.job_id!);
        }, POLL_INTERVAL);
      }
    }).catch(() => {});
  }, [projectId, pollStatus]);

  const doRun = async () => {
    setLoading(true);
    setError('');
    setJobStatus(null);

    try {
      const { data } = await deviceSelectionApi.run(projectId);
      setJobStatus({
        job_id: data.job_id,
        status: 'running',
        message: 'Matching BOQ items to devices with GPT-5.2...',
        matched_count: 0,
      });

      pollingRef.current = setInterval(() => {
        pollStatus(data.job_id);
      }, POLL_INTERVAL);
    } catch (err) {
      setLoading(false);
      setError(normalizeError(err).message);
    }
  };

  const handleRun = () => {
    if (!hasSpec) {
      const confirmed = window.confirm(
        'No specification PDF has been uploaded for this project. ' +
        'Device selection will rely entirely on BOQ data — matches may be less accurate without specification context.\n\n' +
        'Continue without spec?'
      );
      if (!confirmed) return;
    }
    doRun();
  };

  const handleDownload = async () => {
    if (!pagination) return;
    setDownloading(true);
    try {
      const { data } = await deviceSelectionApi.getResults(projectId, {
        page: 1,
        limit: pagination.total,
      });
      const allItems = data.data;

      const header = ['BOQ Description', 'Category', 'Selection Type', 'Product Code(s)', 'Description', 'Reason'];
      const rows = allItems.map((item) => [
        csvEscape(item.boq_description || ''),
        csvEscape(item.selectable_category ? formatCategory(item.selectable_category) : ''),
        csvEscape(item.selection_type),
        csvEscape(item.product_codes.join(', ')),
        csvEscape(item.selectable_description || ''),
        csvEscape(item.reason || ''),
      ]);
      const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');

      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = projectName.replace(/[^a-zA-Z0-9_-]/g, '_') || 'project';
      a.download = `${safeName}-device-selection.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setDownloading(false);
    }
  };

  const NETWORK_CYCLE: Record<string, string> = { wired: 'fiber', fiber: 'IP', IP: 'wired' };

  const handleNetworkTypeSwitch = async () => {
    if (!networkType) return;
    const next = NETWORK_CYCLE[networkType] || 'wired';
    setNetworkSaving(true);
    try {
      await deviceSelectionApi.overrideNetworkType(projectId, next);
      setNetworkType(next);
    } catch (err) {
      console.error('Failed to override network type:', normalizeError(err).message);
    } finally {
      setNetworkSaving(false);
    }
  };

  const isNetworkManuallyChanged = networkType && networkTypeAuto && networkType !== networkTypeAuto;

  return (
    <div className="space-y-4">
      {/* Header row with title + run button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Device Selection</h2>
          <p className="text-sm text-gray-500">
            Match BOQ items to detection devices and notification appliances
          </p>
        </div>
        <Button
          variant="primary"
          onClick={handleRun}
          disabled={loading}
          isLoading={loading}
        >
          <Cpu className="mr-2 h-4 w-4" />
          {loading ? 'Running...' : 'Run Device Selection'}
        </Button>
      </div>

      {/* Status indicators */}
      {loading && jobStatus && (
        <Card>
          <div className="flex items-center justify-center gap-2 py-4 text-sm text-indigo-600">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>{jobStatus.message}</span>
          </div>
          <p className="pb-4 text-center text-xs text-gray-400">
            This may take 1-3 minutes depending on the number of BOQ items.
          </p>
        </Card>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {jobStatus?.status === 'success' && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
          <CheckCircle className="h-4 w-4 flex-shrink-0" />
          <span className="font-medium">
            Device selection complete. {jobStatus.matched_count} items matched.
          </span>
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs font-medium uppercase text-gray-500">
                  <th className="px-4 py-3">BOQ Description</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Product Code(s)</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {results.map((item) => (
                  <tr key={item.boq_item_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900">
                      {item.boq_description || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {item.selectable_category
                        ? formatCategory(item.selectable_category)
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <TypeBadge type={item.selection_type} status={item.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {item.product_codes.length > 0
                        ? item.product_codes.join(', ')
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {item.selectable_description || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-xs">
                      {item.reason ? (
                        <button
                          type="button"
                          onClick={() => toggleReason(item.boq_item_id)}
                          className="text-left cursor-pointer hover:text-gray-900"
                        >
                          <span className={expandedReasons.has(item.boq_item_id) ? '' : 'line-clamp-2'}>
                            {item.reason}
                          </span>
                        </button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination + Download */}
          <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
            <p className="text-sm text-gray-500">
              {pagination && pagination.total_pages > 1
                ? `Showing ${(currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, pagination.total)} of ${pagination.total} items`
                : `${pagination?.total ?? results.length} items`}
            </p>
            <div className="flex gap-2">
              {pagination && pagination.total_pages > 1 && (
                <>
                  <button
                    onClick={() => fetchResults(currentPage - 1)}
                    disabled={currentPage <= 1 || resultsLoading}
                    className="inline-flex items-center rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <ChevronLeft className="mr-1 h-4 w-4" />
                    Previous
                  </button>
                  <button
                    onClick={() => fetchResults(currentPage + 1)}
                    disabled={currentPage >= pagination.total_pages || resultsLoading}
                    className="inline-flex items-center rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </button>
                </>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownload}
                disabled={downloading}
                isLoading={downloading}
              >
                <Download className="mr-1 h-4 w-4" />
                Download CSV
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Network type override — only when network_type has a value */}
      {networkType && results.length > 0 && (
        <div
          className={`rounded-lg border px-4 py-3 ${
            networkType === 'wired'
              ? 'border-blue-200 bg-blue-50'
              : networkType === 'fiber'
                ? 'border-purple-200 bg-purple-50'
                : 'border-teal-200 bg-teal-50'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={`text-sm font-medium ${
                  networkType === 'wired'
                    ? 'text-blue-800'
                    : networkType === 'fiber'
                      ? 'text-purple-800'
                      : 'text-teal-800'
                }`}
              >
                Network Type:
              </span>
              <span
                className={`text-base font-bold ${
                  networkType === 'wired'
                    ? 'text-blue-800'
                    : networkType === 'fiber'
                      ? 'text-purple-800'
                      : 'text-teal-800'
                }`}
              >
                {networkType === 'IP' ? 'IP' : networkType.charAt(0).toUpperCase() + networkType.slice(1)}
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNetworkTypeSwitch}
              disabled={networkSaving}
              isLoading={networkSaving}
            >
              <RefreshCw className="mr-1 h-3 w-3" />
              Switch to {NETWORK_CYCLE[networkType] === 'IP' ? 'IP' : (NETWORK_CYCLE[networkType] || '').charAt(0).toUpperCase() + (NETWORK_CYCLE[networkType] || '').slice(1)}
            </Button>
          </div>
          {isNetworkManuallyChanged && (
            <p className="mt-2 text-xs text-amber-700">
              System suggested <span className="font-semibold">{networkTypeAuto === 'IP' ? 'IP' : networkTypeAuto!.charAt(0).toUpperCase() + networkTypeAuto!.slice(1)}</span>, manually
              changed to <span className="font-semibold">{networkType === 'IP' ? 'IP' : networkType.charAt(0).toUpperCase() + networkType.slice(1)}</span>
            </p>
          )}
        </div>
      )}

      {/* Empty state */}
      {!loading && results.length === 0 && !error && (
        <Card>
          <div className="flex flex-col items-center py-12 text-center">
            <Cpu className="mb-3 h-10 w-10 text-gray-300" />
            <h3 className="text-lg font-semibold text-gray-900">No device selections yet</h3>
            <p className="mt-1 max-w-md text-sm text-gray-500">
              Click "Run Device Selection" to match BOQ items to detection devices and
              notification appliances using AI.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function formatCategory(cat: string): string {
  const map: Record<string, string> = {
    mx_detection_device: 'MX Detection',
    idnet_detection_device: 'IDNet Detection',
    addressable_notification_device: 'Addressable Notification',
    non_addressable_notification_device: 'Non-Addr. Notification',
    conventional_device: 'Conventional',
    annunciator_subpanel: 'Annunciator / Subpanel',
  };
  return map[cat] || cat.replace(/_/g, ' ');
}

function TypeBadge({ type, status }: { type: string; status?: string }) {
  if (status === 'pending_panel') {
    return (
      <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
        pending
      </span>
    );
  }

  const styles: Record<string, string> = {
    single: 'bg-blue-100 text-blue-700',
    combo: 'bg-purple-100 text-purple-700',
    none: 'bg-gray-100 text-gray-500',
  };

  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${styles[type] || styles.none}`}
    >
      {type}
    </span>
  );
}
