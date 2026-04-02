import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';

import { analysisApi } from '../api/analysis.api';
import type { AnalysisAnswerResponse } from '../types/analysis';
import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

interface AnalysisSectionProps {
  projectId: string;
  refreshKey: number;
}

const answerVariant: Record<string, 'success' | 'danger'> = {
  Yes: 'success',
  No: 'danger',
};

const confidenceVariant: Record<string, 'success' | 'warning' | 'danger'> = {
  High: 'success',
  Medium: 'warning',
  Low: 'danger',
};

const sourceVariant: Record<string, 'default' | 'success' | 'warning'> = {
  BOQ: 'default',
  Specs: 'success',
  Both: 'warning',
};

export function AnalysisSection({ projectId, refreshKey }: AnalysisSectionProps) {
  const [answers, setAnswers] = useState<AnalysisAnswerResponse[]>([]);
  const [hasResults, setHasResults] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [finalProtocol, setFinalProtocol] = useState<string | null>(null);
  const [protocolAuto, setProtocolAuto] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchResults = useCallback(async () => {
    setFetching(true);
    try {
      const { data } = await analysisApi.getResults(projectId);
      if (data.status === 'success' && data.answers.length > 0) {
        setAnswers(data.answers);
        setHasResults(true);
        setFinalProtocol(data.final_protocol);
        setProtocolAuto(data.protocol_auto);
      } else {
        setAnswers([]);
        setHasResults(false);
        setFinalProtocol(null);
        setProtocolAuto(null);
      }
    } catch {
      // No results yet
    } finally {
      setFetching(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults, refreshKey]);

  const handleProtocolToggle = async () => {
    if (!finalProtocol) return;
    const newProtocol = finalProtocol === 'MX' ? 'IDNET' : 'MX';
    setSaving(true);
    try {
      await analysisApi.overrideProtocol(projectId, newProtocol);
      setFinalProtocol(newProtocol);
    } catch (err) {
      console.error('Failed to override protocol:', normalizeError(err).message);
    } finally {
      setSaving(false);
    }
  };

  const isManuallyChanged = finalProtocol && protocolAuto && finalProtocol !== protocolAuto;

  if (fetching) {
    return (
      <Card>
        <div className="flex items-center justify-center py-8 text-gray-400">
          Loading analysis...
        </div>
      </Card>
    );
  }

  if (!hasResults) {
    return (
      <Card>
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Protocol Decision Analysis</h2>
        <p className="text-sm text-gray-500">
          No results yet. Run the spec analysis to get AI-powered answers.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Protocol Decision Analysis</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs uppercase text-gray-500">
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Question</th>
              <th className="px-3 py-2">Answer</th>
              <th className="px-3 py-2">Confidence</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Supporting Evidence</th>
            </tr>
          </thead>
          <tbody>
            {answers.map((a) => (
              <tr key={a.id} className="border-b border-gray-100">
                <td className="px-3 py-3 font-medium text-gray-700">{a.question_no}</td>
                <td className="max-w-xs px-3 py-3 text-gray-700">{a.question_text}</td>
                <td className="px-3 py-3">
                  <Badge variant={answerVariant[a.answer] ?? 'default'}>{a.answer}</Badge>
                </td>
                <td className="px-3 py-3">
                  <Badge variant={confidenceVariant[a.confidence] ?? 'default'}>
                    {a.confidence}
                  </Badge>
                </td>
                <td className="px-3 py-3">
                  <Badge variant={sourceVariant[a.inferred_from] ?? 'default'}>
                    {a.inferred_from}
                  </Badge>
                </td>
                <td className="px-3 py-3">
                  <ul className="list-inside list-disc space-y-1 text-xs text-gray-600">
                    {a.supporting_notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {finalProtocol && (
        <div
          className={`mt-4 rounded-lg border px-4 py-3 ${
            finalProtocol === 'MX'
              ? 'border-blue-200 bg-blue-50'
              : 'border-emerald-200 bg-emerald-50'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={`text-sm font-medium ${
                  finalProtocol === 'MX' ? 'text-blue-800' : 'text-emerald-800'
                }`}
              >
                Final Protocol:
              </span>
              <span
                className={`text-base font-bold ${
                  finalProtocol === 'MX' ? 'text-blue-800' : 'text-emerald-800'
                }`}
              >
                {finalProtocol}
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleProtocolToggle}
              disabled={saving}
              isLoading={saving}
            >
              <RefreshCw className="mr-1 h-3 w-3" />
              Switch to {finalProtocol === 'MX' ? 'IDNET' : 'MX'}
            </Button>
          </div>
          {isManuallyChanged && (
            <p className="mt-2 text-xs text-amber-700">
              Analysis suggests <span className="font-semibold">{protocolAuto}</span>, manually
              changed to <span className="font-semibold">{finalProtocol}</span>
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
