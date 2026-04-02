import { useCallback, useEffect, useRef, useState } from 'react';
import { FileSpreadsheet, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

import { boqExtractionApi } from '../api/boq-extraction.api';
import type { BoqExtractionJobStatus } from '../types/boq-extraction';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

interface BoqExtractionSectionProps {
  projectId: string;
  hasBoq: boolean;
  onExtractionComplete: () => void;
}

const POLL_INTERVAL = 3000;

export function BoqExtractionSection({
  projectId,
  hasBoq,
  onExtractionComplete,
}: BoqExtractionSectionProps) {
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<BoqExtractionJobStatus | null>(null);
  const [error, setError] = useState('');
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const canRun = hasBoq && !loading;

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(
    async (jid: string) => {
      try {
        const { data } = await boqExtractionApi.getStatus(projectId, jid);
        setJobStatus(data);

        if (data.status === 'success') {
          stopPolling();
          setLoading(false);
          onExtractionComplete();
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
    [projectId, stopPolling, onExtractionComplete],
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // Check for active job on mount (resume polling if user navigated away)
  useEffect(() => {
    boqExtractionApi.getActiveJob(projectId).then(({ data }) => {
      if (data.active && data.job_id) {
        setLoading(true);
        setJobStatus({
          job_id: data.job_id,
          status: data.status as 'running',
          message: data.message || 'Extracting BOQ items...',
          boq_items_count: 0,
        });
        pollingRef.current = setInterval(() => {
          pollStatus(data.job_id!);
        }, POLL_INTERVAL);
      }
    }).catch(() => {});
  }, [projectId, pollStatus]);

  const handleRun = async () => {
    setLoading(true);
    setError('');
    setJobStatus(null);

    try {
      const { data } = await boqExtractionApi.run(projectId);
      setJobStatus({
        job_id: data.job_id,
        status: 'running',
        message: 'Extracting BOQ items with GPT-5.2...',
        boq_items_count: 0,
      });

      pollingRef.current = setInterval(() => {
        pollStatus(data.job_id);
      }, POLL_INTERVAL);
    } catch (err) {
      setLoading(false);
      setError(normalizeError(err).message);
    }
  };

  return (
    <Card>
      <div className="flex flex-col items-center py-6 text-center">
        <FileSpreadsheet className="mb-3 h-10 w-10 text-blue-500" />
        <h3 className="text-lg font-semibold text-gray-900">Extract BOQ</h3>
        <p className="mt-1 max-w-md text-sm text-gray-500">
          Extract BOQ items from the uploaded document and label each item with a
          fire-protection category.
        </p>

        {!hasBoq && (
          <p className="mt-3 text-xs text-amber-600">
            Upload a BOQ document first.
          </p>
        )}

        <div className="mt-4">
          <Button
            variant="primary"
            size="lg"
            onClick={handleRun}
            disabled={!canRun}
            isLoading={loading}
          >
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            {loading ? 'Extracting...' : 'Extract BOQ'}
          </Button>
        </div>

        {loading && jobStatus && (
          <div className="mt-4 w-full max-w-sm">
            <div className="flex items-center justify-center gap-2 text-sm text-blue-600">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>{jobStatus.message}</span>
            </div>
            <p className="mt-2 text-xs text-gray-400">
              This may take 1-3 minutes depending on document size.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {jobStatus && jobStatus.status === 'success' && (
          <div className="mt-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              <span className="font-medium">BOQ Extraction Complete</span>
            </div>
            <p className="mt-1 text-xs">
              {jobStatus.boq_items_count} BOQ items extracted and categorized.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
