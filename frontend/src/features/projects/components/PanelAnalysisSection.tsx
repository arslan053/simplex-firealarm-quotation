import { useCallback, useEffect, useState } from 'react';

import { panelAnalysisApi } from '../api/panel-analysis.api';
import type { PanelAnalysisAnswerResponse, PanelResult } from '../types/panel-analysis';
import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';

interface PanelAnalysisSectionProps {
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

export function PanelAnalysisSection({ projectId, refreshKey }: PanelAnalysisSectionProps) {
  const [answers, setAnswers] = useState<PanelAnalysisAnswerResponse[]>([]);
  const [hasResults, setHasResults] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [panelResult, setPanelResult] = useState<PanelResult | null>(null);

  const fetchResults = useCallback(async () => {
    setFetching(true);
    try {
      const { data } = await panelAnalysisApi.getResults(projectId);
      if (data.status === 'success' && data.answers.length > 0) {
        setAnswers(data.answers);
        setHasResults(true);
        setPanelResult(data.panel_result);
      } else {
        setAnswers([]);
        setHasResults(false);
        setPanelResult(null);
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

  if (fetching) {
    return (
      <Card>
        <div className="flex items-center justify-center py-8 text-gray-400">
          Loading panel analysis...
        </div>
      </Card>
    );
  }

  if (!hasResults) {
    return (
      <Card>
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Panel Selection Analysis</h2>
        <p className="text-sm text-gray-500">
          No results yet. Run the spec analysis to determine panel configuration.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Panel Selection Analysis</h2>

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

      {panelResult && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-violet-200 bg-violet-50 px-4 py-3 text-violet-800">
          <span className="text-sm font-medium">Panel Calculation:</span>
          <span className="text-base font-bold">{panelResult.label}</span>
        </div>
      )}
    </Card>
  );
}
