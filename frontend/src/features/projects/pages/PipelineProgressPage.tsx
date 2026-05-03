import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Loader2,
  Circle,
  RefreshCw,
  Lightbulb,
} from 'lucide-react';

import { pipelineApi } from '../api/pipeline.api';
import { projectsApi } from '../api/projects.api';
import type { PipelineStatus } from '../types/pipeline';
import { PIPELINE_STEPS } from '../types/pipeline';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

const POLL_INTERVAL = 4000;
const TIP_INTERVAL = 12000;

const TIPS = [
  'You can close this page and come back anytime. Your analysis continues in the background.',
  'The system is extracting items from your Bill of Quantities...',
  'Analyzing specifications and determining system protocol...',
  'Matching BOQ items to the best products...',
  'Configuring panel products and accessories...',
  'Calculating pricing for all selected products...',
  'Generating your final quotation document...',
];

const STEP_TIPS: Record<string, string> = {
  boq_extraction: 'Extracting and categorizing items from your BOQ documents...',
  spec_analysis: 'Analyzing your specification to determine protocol and requirements...',
  device_selection: 'Matching each BOQ item to the best Simplex product...',
  panel_selection: 'Configuring fire alarm panel with required cards and accessories...',
  pricing: 'Looking up prices and calculating totals for all selected products...',
  quotation_generation: 'Building your final quotation document with all details...',
};

export function PipelineProgressPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [projectName, setProjectName] = useState('');
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState('');
  const [tipIndex, setTipIndex] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tipRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    if (!projectId) return;
    try {
      const { data } = await pipelineApi.getStatus(projectId);
      setPipelineStatus(data);

      if (data.status === 'completed') {
        stopPolling();
        // Small delay before navigating to show completion
        setTimeout(() => {
          navigate(`/projects/${projectId}/completed`, { replace: true });
        }, 1500);
      } else if (data.status === 'failed') {
        stopPolling();
      }
    } catch {
      // Pipeline may not exist yet — redirect to setup
      navigate(`/projects/${projectId}/setup`, { replace: true });
    }
  }, [projectId, navigate, stopPolling]);

  useEffect(() => {
    if (!projectId) return;
    projectsApi.get(projectId).then(({ data }) => {
      setProjectName(data.project_name);
    }).catch(() => {});

    fetchStatus();
    pollingRef.current = setInterval(fetchStatus, POLL_INTERVAL);

    return () => {
      stopPolling();
    };
  }, [projectId, fetchStatus, stopPolling]);

  // Rotating tips
  useEffect(() => {
    tipRef.current = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % TIPS.length);
    }, TIP_INTERVAL);
    return () => {
      if (tipRef.current) clearInterval(tipRef.current);
    };
  }, []);

  const handleRetry = async () => {
    if (!projectId) return;
    setRetrying(true);
    setError('');
    try {
      await pipelineApi.retry(projectId);
      // Restart polling
      pollingRef.current = setInterval(fetchStatus, POLL_INTERVAL);
      fetchStatus();
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setRetrying(false);
    }
  };

  const currentStep = pipelineStatus?.current_step;
  const currentTip = currentStep && STEP_TIPS[currentStep]
    ? STEP_TIPS[currentStep]
    : TIPS[tipIndex];

  if (!projectId) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/projects')}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
        >
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {pipelineStatus?.status === 'completed'
              ? 'Analysis Complete'
              : pipelineStatus?.status === 'failed'
                ? 'Analysis Failed'
                : 'Project Analysis in Progress'}
          </h1>
          {projectName && (
            <p className="mt-1 text-sm text-gray-500">{projectName}</p>
          )}
        </div>
      </div>

      {/* Steps */}
      <Card>
        <div className="space-y-1">
          {PIPELINE_STEPS.map(({ key, label }) => {
            const isCompleted = pipelineStatus?.steps_completed.includes(key);
            const isRunning = pipelineStatus?.current_step === key && pipelineStatus?.status === 'running';
            const isFailed = pipelineStatus?.error_step === key && pipelineStatus?.status === 'failed';

            let icon;
            let textColor;

            if (isCompleted) {
              icon = <CheckCircle className="h-5 w-5 text-green-500" />;
              textColor = 'text-green-700';
            } else if (isRunning) {
              icon = <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />;
              textColor = 'text-indigo-700 font-medium';
            } else if (isFailed) {
              icon = <XCircle className="h-5 w-5 text-red-500" />;
              textColor = 'text-red-700';
            } else {
              icon = <Circle className="h-5 w-5 text-gray-300" />;
              textColor = 'text-gray-400';
            }

            return (
              <div
                key={key}
                className={`flex items-center gap-3 rounded-lg px-4 py-3 ${
                  isRunning
                    ? 'bg-indigo-50'
                    : isFailed
                      ? 'bg-red-50'
                      : ''
                }`}
              >
                {icon}
                <span className={`text-sm ${textColor}`}>{label}</span>
                {isRunning && (
                  <span className="ml-auto text-xs text-indigo-500">
                    Running...
                  </span>
                )}
                {isCompleted && (
                  <span className="ml-auto text-xs text-green-500">
                    Complete
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Error details */}
        {pipelineStatus?.status === 'failed' && pipelineStatus.error_message && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="mt-1 text-sm text-red-700">
              {pipelineStatus.error_message}
            </p>
          </div>
        )}
      </Card>

      {/* Tip card */}
      {pipelineStatus?.status === 'running' && (
        <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-4">
          <div className="flex items-start gap-3">
            <Lightbulb className="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-500" />
            <p className="text-sm text-indigo-700">{currentTip}</p>
          </div>
        </div>
      )}

      {/* Actions */}
      {pipelineStatus?.status === 'failed' && (
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => navigate(`/projects/${projectId}/setup`)}>
            Back to Setup
          </Button>
          <Button onClick={handleRetry} isLoading={retrying}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry from Failed Step
          </Button>
        </div>
      )}

      {pipelineStatus?.status === 'completed' && (
        <div className="text-center">
          <p className="mb-3 text-sm text-green-600">
            Analysis complete! Redirecting to results...
          </p>
          <Button
            onClick={() =>
              navigate(`/projects/${projectId}/completed`, { replace: true })
            }
          >
            View Results
          </Button>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
