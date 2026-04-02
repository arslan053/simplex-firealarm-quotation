import { useCallback, useEffect, useRef, useState } from 'react';
import { Zap, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

import { specAnalysisApi } from '../api/spec-analysis.api';
import type { SpecAnalysisJobStatus } from '../types/spec-analysis';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

interface SpecAnalysisSectionProps {
  projectId: string;
  hasSpec: boolean;
  hasBoqExtracted: boolean;
  onAnalysisComplete: () => void;
}

const POLL_INTERVAL = 3000;

export function SpecAnalysisSection({
  projectId,
  hasSpec,
  hasBoqExtracted,
  onAnalysisComplete,
}: SpecAnalysisSectionProps) {
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<SpecAnalysisJobStatus | null>(null);
  const [error, setError] = useState('');
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const canRun = hasBoqExtracted && !loading;

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(
    async (jid: string) => {
      try {
        const { data } = await specAnalysisApi.getStatus(projectId, jid);
        setJobStatus(data);

        if (data.status === 'success') {
          stopPolling();
          setLoading(false);
          onAnalysisComplete();
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
    [projectId, stopPolling, onAnalysisComplete],
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // Check for active job on mount (resume polling if user navigated away)
  useEffect(() => {
    specAnalysisApi.getActiveJob(projectId).then(({ data }) => {
      if (data.active && data.job_id) {
        setLoading(true);
        setJobStatus({
          job_id: data.job_id,
          status: data.status as 'running',
          message: data.message || 'Analyzing spec...',
          spec_blocks_count: 0,
          answers_count: 0,
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
      const { data } = await specAnalysisApi.run(projectId);
      setJobStatus({
        job_id: data.job_id,
        status: 'running',
        message: hasSpec
          ? 'Analyzing spec & answering questions with GPT-5.2...'
          : 'Answering questions from BOQ data (no spec) with GPT-5.2...',
        spec_blocks_count: 0,
        answers_count: 0,
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
        'The analysis will rely entirely on BOQ data — answers may be less accurate without specification context.\n\n' +
        'Continue without spec?'
      );
      if (!confirmed) return;
    }
    doRun();
  };

  return (
    <Card>
      <div className="flex flex-col items-center py-6 text-center">
        <Zap className="mb-3 h-10 w-10 text-indigo-400" />
        <h3 className="text-lg font-semibold text-gray-900">Run Analysis</h3>
        <p className="mt-1 max-w-md text-sm text-gray-500">
          Convert the specification PDF to markdown and answer all analysis questions
          using the extracted BOQ data.
        </p>

        {!hasBoqExtracted && (
          <p className="mt-3 text-xs text-amber-600">
            Extract BOQ items first.
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
            <Zap className="mr-2 h-4 w-4" />
            {loading ? 'Analyzing...' : 'Run Analysis'}
          </Button>
        </div>

        {loading && jobStatus && (
          <div className="mt-4 w-full max-w-sm">
            <div className="flex items-center justify-center gap-2 text-sm text-indigo-600">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>{jobStatus.message}</span>
            </div>
            <p className="mt-2 text-xs text-gray-400">
              This may take 2-5 minutes depending on document size.
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
              <span className="font-medium">Analysis Complete</span>
            </div>
            <p className="mt-1 text-xs">
              {jobStatus.spec_blocks_count} spec blocks parsed,{' '}
              {jobStatus.answers_count} questions answered.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
