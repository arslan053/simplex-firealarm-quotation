import { useCallback, useEffect, useRef, useState } from 'react';
import { Cpu, Loader2, AlertCircle, CheckCircle, XCircle, Download, ChevronDown, ChevronUp } from 'lucide-react';

import { panelSelectionApi } from '../api/panel-selection.api';
import type { PanelGroupResult, PanelQuestionAnswer, PanelSelectionJobStatus, PanelSelectionResults } from '../types/panel-selection';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

const POLL_INTERVAL = 3000;

const PANEL_QUESTIONS: Record<string, number[]> = {
  '4007': [2, 3, 21, 14, 17, 18, 20],
  '4010_1bay': [2, 3, 21, 14, 17, 18, 204],
  '4010_2bay': [2, 3, 21, 14, 17, 18, 204],
  '4100ES': [2, 3, 21, 14, 201, 202, 203, 204, 206],
};

function getActionText(qNo: number, answer: string | null | undefined): string {
  const a = (answer ?? '').trim().toLowerCase();

  switch (qNo) {
    case 2:
      return a === 'yes'
        ? 'Triggers 4100ES entry — speakers required'
        : 'No speakers — no effect on panel decision';
    case 3:
      return a === 'yes'
        ? 'Triggers 4100ES entry — telephone required'
        : 'No telephone — no effect on panel decision';
    case 21: {
      if (!a || a === 'null' || a === 'n/a' || a === 'none')
        return 'Loop count not specified — no effect';
      const n = parseInt(a.replace(/[^\d]/g, ''), 10);
      if (isNaN(n)) return 'Loop count not specified — no effect';
      if (n <= 2) return 'Within 4007 range (up to 2 loops) — no effect';
      if (n <= 6) return 'Exceeds 4007 limit (2 loops) — upgrades to 4010';
      return 'Exceeds 4010 limit (6 loops) — triggers 4100ES';
    }
    case 14:
      return a === 'yes'
        ? 'Add printer card (if no workstation in project)'
        : 'No printer needed';
    case 17:
      return a === 'yes'
        ? 'Add repeater panel / LCD annunciator child cards'
        : 'No repeater panel needed';
    case 18:
      return a === 'yes'
        ? 'Add graphic annunciator child cards'
        : 'No graphic annunciator needed';
    case 20:
      return a === 'yes'
        ? 'Add panel-mounted annunciator child card'
        : 'No panel-mounted annunciator needed';
    case 201:
      return a === 'yes'
        ? 'Select touchscreen controller (4100-9706)'
        : 'Select standard LCD controller (4100-9701)';
    case 202:
      return a === 'yes'
        ? 'Use backup amplifiers (4100-1327, 50W, ceil(speakers/50))'
        : 'Use standard amplifiers (4100-1333, 100W, ceil(speakers/100))';
    case 203:
      return a === 'yes'
        ? 'Add Class A wiring adapters for amps and phone controllers'
        : 'No Class A adapters needed';
    case 204:
      return a === 'yes'
        ? 'Add BMS integration card'
        : 'No BMS integration';
    case 206: {
      const n = parseInt(a.replace(/[^\d]/g, ''), 10);
      if (isNaN(n) || n === 0) return 'No phone jacks found';
      return `Phone jack count → ceil(${n}/45) phone controllers`;
    }
    default:
      return '';
  }
}

function AnswerBadge({ answer }: { answer: string }) {
  const a = answer.trim().toLowerCase();
  let style = 'bg-gray-100 text-gray-600';
  if (a === 'yes') style = 'bg-green-100 text-green-700';
  else if (a === 'no') style = 'bg-gray-100 text-gray-600';
  else if (/^\d+$/.test(a)) style = 'bg-blue-100 text-blue-700';
  else if (a === 'null' || a === 'n/a' || a === 'none' || !a)
    style = 'bg-gray-50 text-gray-400';

  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {answer || '—'}
    </span>
  );
}

interface PanelConfigurationSectionProps {
  projectId: string;
  onPanelComplete?: () => void;
  hasSpec?: boolean;
  readOnly?: boolean;
}

export function PanelConfigurationSection({ projectId, onPanelComplete, hasSpec = true, readOnly = false }: PanelConfigurationSectionProps) {
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<PanelSelectionJobStatus | null>(null);
  const [error, setError] = useState('');
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [results, setResults] = useState<PanelSelectionResults | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [answers, setAnswers] = useState<PanelQuestionAnswer[]>([]);
  const [answersExpanded, setAnswersExpanded] = useState(false);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const fetchResults = useCallback(async () => {
    try {
      const { data } = await panelSelectionApi.getResults(projectId);
      setResults(data);
    } catch (err) {
      setError(normalizeError(err).message);
    }
  }, [projectId]);

  const fetchAnswers = useCallback(async () => {
    try {
      const { data } = await panelSelectionApi.getAnswers(projectId);
      setAnswers(data.answers);
    } catch {
      // Non-critical — don't block the page
    }
  }, [projectId]);

  const pollStatus = useCallback(
    async (jid: string) => {
      try {
        const { data } = await panelSelectionApi.getStatus(projectId, jid);
        setJobStatus(data);

        if (data.status === 'success') {
          stopPolling();
          setLoading(false);
          fetchResults();
          fetchAnswers();
          onPanelComplete?.();
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
    [projectId, stopPolling, fetchResults, fetchAnswers, onPanelComplete],
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  useEffect(() => {
    fetchResults();
    fetchAnswers();
  }, [fetchResults, fetchAnswers]);

  // Check for active job on mount (resume polling if user navigated away)
  useEffect(() => {
    panelSelectionApi.getActiveJob(projectId).then(({ data }) => {
      if (data.active && data.job_id) {
        setLoading(true);
        setJobStatus({
          job_id: data.job_id,
          status: data.status as 'running',
          message: data.message || 'Analyzing BOQ for panel configuration...',
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
      const { data } = await panelSelectionApi.run(projectId);
      setJobStatus({
        job_id: data.job_id,
        status: 'running',
        message: 'Analyzing BOQ for panel configuration...',
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
        'Panel selection will rely entirely on BOQ data — results may be less accurate without specification context.\n\n' +
        'Continue without spec?'
      );
      if (!confirmed) return;
    }
    doRun();
  };

  const handleDownload = () => {
    if (!results || !results.products.length) return;
    setDownloading(true);
    try {
      const header = ['Product Code', 'Description', 'Qty', 'Source', 'Reason'];
      const csvRows: string[] = [header.join(',')];

      if (results.is_multi_group && results.panel_groups?.length) {
        for (const group of results.panel_groups) {
          csvRows.push('');
          csvRows.push(
            csvEscape(
              `${group.is_main ? '[MAIN] ' : ''}${group.panel_label} — ${group.boq_description || 'Group'} (${group.loop_count} loops x ${group.quantity})`
            )
          );
          for (const p of group.products) {
            csvRows.push(
              [
                csvEscape(p.product_code),
                csvEscape(p.product_name || ''),
                String(p.quantity),
                csvEscape(formatSource(p.source)),
                csvEscape(p.reason || ''),
              ].join(',')
            );
          }
        }
      } else {
        for (const p of results.products) {
          csvRows.push(
            [
              csvEscape(p.product_code),
              csvEscape(p.product_name || ''),
              String(p.quantity),
              csvEscape(formatSource(p.source)),
              csvEscape(p.reason || ''),
            ].join(',')
          );
        }
      }

      const csv = csvRows.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'panel-configuration.csv';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const showResults = results && results.status !== 'empty';
  const panelSupported = results?.panel_supported ?? false;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Panel Configuration</h2>
          <p className="text-sm text-gray-500">
            Determine panel type, base unit and child cards from BOQ analysis
          </p>
        </div>
        {!readOnly && (
          <Button variant="primary" onClick={handleRun} disabled={loading} isLoading={loading}>
            <Cpu className="mr-2 h-4 w-4" />
            {loading ? 'Running...' : 'Run Panel Selection'}
          </Button>
        )}
      </div>

      {/* Loading */}
      {loading && jobStatus && (
        <Card>
          <div className="flex items-center justify-center gap-2 py-4 text-sm text-indigo-600">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>{jobStatus.message}</span>
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

      {/* Gate Fail Result */}
      {showResults && !panelSupported && (
        <Card>
          <div className="px-4 py-4">
            <div className="flex items-center gap-2 text-red-700">
              <XCircle className="h-5 w-5 flex-shrink-0" />
              <span className="font-semibold">Panel Not Supported</span>
            </div>
            <p className="mt-2 text-sm text-gray-600">{results?.message}</p>
            {results?.gate_result && (
              <div className="mt-3 space-y-1 text-sm">
                <GateRow
                  label={q1Label(results.gate_result)}
                  passed={results.gate_result.q1_passed}
                  detail={q1Detail(results.gate_result)}
                />
                {results.gate_result.mx_addressable_blocked && (
                  <GateRow
                    label="MX + Addressable notification"
                    passed={false}
                    detail="Not supported for 4010 panels"
                  />
                )}
                <GateRow
                  label="Q2: Speakers/Amplifiers required?"
                  passed={results.gate_result.q2_passed}
                  detail={results.gate_result.q2_answer ?? 'N/A'}
                />
                <GateRow
                  label="Q3: Telephone/FFT required?"
                  passed={results.gate_result.q3_passed}
                  detail={results.gate_result.q3_answer ?? 'N/A'}
                />
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Success + Products */}
      {showResults && panelSupported && (
        <>
          <div className="flex items-center gap-2 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
            <span className="font-medium">{results?.message}</span>
            {results?.gate_result.panel_label && (
              <span className="ml-2 inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                {results.gate_result.panel_label}
              </span>
            )}
          </div>

          {results?.gate_result && (
            <Card>
              <div className="px-4 py-3 space-y-1 text-sm">
                {results.gate_result.is_4100es ? (
                  <>
                    <p className="font-medium text-gray-700 mb-2">4100ES Entry Conditions</p>
                    {results.gate_result.entry_reasons?.map((reason, i) => (
                      <GateRow key={i} label={reason} passed={true} detail="Matched" />
                    ))}
                  </>
                ) : (
                  <>
                    <p className="font-medium text-gray-700 mb-2">Gate Checks</p>
                    <GateRow
                      label={q1Label(results.gate_result)}
                      passed={results.gate_result.q1_passed}
                      detail={q1Detail(results.gate_result)}
                    />
                    <GateRow
                      label="Q2: Speakers/Amplifiers required?"
                      passed={results.gate_result.q2_passed}
                      detail={results.gate_result.q2_answer ?? 'N/A'}
                    />
                    <GateRow
                      label="Q3: Telephone/FFT required?"
                      passed={results.gate_result.q3_passed}
                      detail={results.gate_result.q3_answer ?? 'N/A'}
                    />
                  </>
                )}
              </div>
            </Card>
          )}

          {answers.length > 0 && results?.gate_result && (
            <QASection
              answers={answers}
              panelType={results.gate_result.panel_type}
              expanded={answersExpanded}
              onToggle={() => setAnswersExpanded((v) => !v)}
            />
          )}

          {results?.is_multi_group && results.panel_groups && results.panel_groups.length > 0 ? (
            <>
              {results.panel_groups.map((group) => (
                <PanelGroupSection key={group.id} group={group} />
              ))}
              <div className="flex justify-end">
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
            </>
          ) : (
            results?.products && results.products.length > 0 && (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-xs font-medium uppercase text-gray-500">
                        <th className="px-4 py-3">Product Code</th>
                        <th className="px-4 py-3">Description</th>
                        <th className="px-4 py-3 text-center">Qty</th>
                        <th className="px-4 py-3">Source</th>
                        <th className="px-4 py-3">Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {results.products.map((p, idx) => (
                        <tr key={`${p.product_code}-${idx}`} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-gray-900">{p.product_code}</td>
                          <td className="px-4 py-3 text-gray-700">{p.product_name || '—'}</td>
                          <td className="px-4 py-3 text-center font-medium text-gray-900">
                            {p.quantity}
                          </td>
                          <td className="px-4 py-3">
                            <SourceBadge source={p.source} />
                          </td>
                          <td className="px-4 py-3 text-gray-600 max-w-xs">
                            <span className="line-clamp-2">{p.reason || '—'}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex justify-end border-t border-gray-200 px-4 py-3">
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
              </Card>
            )
          )}
        </>
      )}

      {/* Empty state */}
      {!loading && !showResults && !error && (
        <Card>
          <div className="flex flex-col items-center py-12 text-center">
            <Cpu className="mb-3 h-10 w-10 text-gray-300" />
            <h3 className="text-lg font-semibold text-gray-900">No panel configuration yet</h3>
            <p className="mt-1 max-w-md text-sm text-gray-500">
              Click &quot;Run Panel Selection&quot; to determine the panel configuration
              based on BOQ analysis.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

function PanelGroupSection({ group }: { group: PanelGroupResult }) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-gray-900">
            {group.boq_description || `${group.loop_count}-Loop Panel`}
          </span>
          <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
            {group.panel_label}
          </span>
          <span className="text-sm text-gray-500">
            {group.loop_count} loops &times; {group.quantity}
          </span>
          {group.is_main && (
            <span className="inline-block rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">
              MAIN PANEL
            </span>
          )}
        </div>
      </div>
      {group.products.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs font-medium uppercase text-gray-500">
                <th className="px-4 py-3">Product Code</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3 text-center">Qty</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {group.products.map((p, idx) => (
                <tr key={`${p.product_code}-${idx}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-900">{p.product_code}</td>
                  <td className="px-4 py-3 text-gray-700">{p.product_name || '\u2014'}</td>
                  <td className="px-4 py-3 text-center font-medium text-gray-900">
                    {p.quantity}
                  </td>
                  <td className="px-4 py-3">
                    <SourceBadge source={p.source} />
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-xs">
                    <span className="line-clamp-2">{p.reason || '\u2014'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function q1Label(g: { q1_total_devices: number; q1_devices_per_panel: number; q1_panel_count: number | null }): string {
  if (g.q1_panel_count && g.q1_panel_count > 1) {
    return `Q1: Devices per panel (${g.q1_total_devices} total / ${g.q1_panel_count} panels = ${g.q1_devices_per_panel})`;
  }
  return `Q1: Devices per panel (${g.q1_devices_per_panel})`;
}

function q1Detail(g: { q1_devices_per_panel: number; q1_passed: boolean; panel_label: string | null }): string {
  if (g.q1_passed && g.panel_label) {
    return `${g.q1_devices_per_panel} → ${g.panel_label}`;
  }
  if (!g.q1_passed) {
    return `${g.q1_devices_per_panel} per panel — no supported panel type`;
  }
  return `${g.q1_devices_per_panel}`;
}

function GateRow({ label, passed, detail }: { label: string; passed: boolean; detail: string }) {
  return (
    <div className="flex items-center gap-2">
      {passed ? (
        <CheckCircle className="h-4 w-4 text-green-500" />
      ) : (
        <XCircle className="h-4 w-4 text-red-500" />
      )}
      <span className="text-gray-700">{label}</span>
      <span className="text-gray-400">—</span>
      <span className={passed ? 'text-green-600' : 'text-red-600'}>{detail}</span>
    </div>
  );
}

function QASection({
  answers,
  panelType,
  expanded,
  onToggle,
}: {
  answers: PanelQuestionAnswer[];
  panelType: string | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const relevantQNos = panelType ? (PANEL_QUESTIONS[panelType] ?? []) : [];
  const filtered = relevantQNos.length > 0
    ? answers.filter((a) => relevantQNos.includes(a.question_no))
    : answers;

  if (filtered.length === 0) return null;

  return (
    <Card>
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <span className="text-sm font-medium text-gray-700">
          LLM Analysis Answers ({filtered.length} questions)
        </span>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="overflow-x-auto border-t border-gray-200">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs font-medium uppercase text-gray-500">
                <th className="px-4 py-2 w-16">Q#</th>
                <th className="px-4 py-2">Question</th>
                <th className="px-4 py-2 w-24 text-center">Answer</th>
                <th className="px-4 py-2">Action Taken</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((a) => (
                <tr key={a.question_no} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-gray-500">Q{a.question_no}</td>
                  <td className="px-4 py-2 text-gray-700 max-w-xs">
                    <span className="line-clamp-2">{a.question}</span>
                  </td>
                  <td className="px-4 py-2 text-center">
                    <AnswerBadge answer={a.answer} />
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {getActionText(a.question_no, a.answer)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function SourceBadge({ source }: { source: string }) {
  const styles: Record<string, string> = {
    base_unit: 'bg-indigo-100 text-indigo-700',
    assistive_card: 'bg-amber-100 text-amber-700',
    child_card: 'bg-blue-100 text-blue-700',
  };

  const style = styles[source]
    || (source.startsWith('step_') ? 'bg-teal-100 text-teal-700' : 'bg-gray-100 text-gray-500');

  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {formatSource(source)}
    </span>
  );
}

function formatSource(source: string): string {
  const map: Record<string, string> = {
    base_unit: 'Base Unit',
    assistive_card: 'Assistive Card',
    child_card: 'Child Card',
  };
  if (map[source]) return map[source];

  // Convert step_4_loop_card → "Step 4: Loop Card"
  const stepMatch = source.match(/^step_(\d+(?:_\d+[a-z]?)?)_(.+)$/);
  if (stepMatch) {
    const stepNum = stepMatch[1].replace('_', '.');
    const label = stepMatch[2]
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
    return `Step ${stepNum}: ${label}`;
  }

  return source.replace(/_/g, ' ');
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
