import React, { useCallback, useEffect, useState } from 'react';
import { Eye, EyeOff, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Download } from 'lucide-react';

import { boqApi } from '../api/boq.api';
import type { BoqItemResponse } from '../types/boq';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { Card } from '@/shared/ui/Card';
import { normalizeError } from '@/shared/api/errors';

interface BoqItemsTableProps {
  projectId: string;
  projectName: string;
  show: boolean;
  onToggleShow: () => void;
  refreshKey: number;
}

const CATEGORY_LABELS: Record<string, string> = {
  detection_devices: 'Detection Devices',
  notification: 'Notification',
  audio_panel: 'Audio Panel',
  special_items: 'Special Items',
  pc_tsw: 'PC-TSW',
  mimic_panel: 'Mimic Panel',
  panel: 'Panel',
  remote_annunciator: 'Remote Annunciator',
  repeater: 'Repeater',
};

const CATEGORY_VARIANTS: Record<string, 'default' | 'success' | 'warning' | 'danger'> = {
  detection_devices: 'success',
  notification: 'default',
  audio_panel: 'warning',
  special_items: 'default',
  pc_tsw: 'default',
  mimic_panel: 'warning',
  panel: 'warning',
  remote_annunciator: 'default',
  repeater: 'default',
};

export function BoqItemsTable({ projectId, projectName, show, onToggleShow, refreshKey }: BoqItemsTableProps) {
  const [items, setItems] = useState<BoqItemResponse[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [downloading, setDownloading] = useState(false);

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const fetchItems = useCallback(async (p: number) => {
    setLoading(true);
    setError('');
    try {
      const { data } = await boqApi.listItems(projectId, { page: p, limit: 50 });
      setItems(data.data);
      setPage(data.pagination.page);
      setTotalPages(data.pagination.total_pages);
      setTotal(data.pagination.total);
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (show) {
      fetchItems(1);
    }
  }, [show, fetchItems, refreshKey]);

  const handleToggleVisibility = async (item: BoqItemResponse) => {
    try {
      const { data } = await boqApi.toggleVisibility(projectId, item.id, !item.is_hidden);
      setItems((prev) =>
        prev.map((i) => (i.id === data.id ? data : i)),
      );
    } catch (err) {
      setError(normalizeError(err).message);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const { data } = await boqApi.listItems(projectId, { page: 1, limit: total || 10000 });
      const allItems = data.data;

      const header = ['Row #', 'Type', 'Description', 'Quantity', 'Unit', 'Category', 'Status'];
      const rows = allItems.map((item) => [
        csvEscape(String(item.row_number)),
        csvEscape(item.type),
        csvEscape(item.description || ''),
        csvEscape(item.quantity != null ? String(item.quantity) : ''),
        csvEscape(item.unit || ''),
        csvEscape(item.category ? (CATEGORY_LABELS[item.category] ?? item.category) : ''),
        csvEscape(item.is_valid ? 'Valid' : 'Invalid'),
      ]);
      const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');

      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = projectName.replace(/[^a-zA-Z0-9_-]/g, '_') || 'project';
      a.download = `${safeName}-boq-extraction.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onToggleShow}>
          {show ? 'Hide BOQ Items' : 'Show BOQ Items'}
        </Button>
        {total > 0 && (
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
        )}
      </div>

      {show && (
        <Card className="mt-4">
          {loading && (
            <div className="flex items-center justify-center py-8 text-gray-500">
              Loading items...
            </div>
          )}

          {error && (
            <p className="mb-4 text-sm text-red-600">{error}</p>
          )}

          {!loading && items.length === 0 && !error && (
            <div className="py-8 text-center text-sm text-gray-500">
              No BOQ items found. Upload a BoQ file and run analysis to extract items.
            </div>
          )}

          {!loading && items.length > 0 && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-xs font-medium uppercase text-gray-500">
                      <th className="px-4 py-3">Row #</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Description</th>
                      <th className="px-4 py-3">Quantity</th>
                      <th className="px-4 py-3">Unit</th>
                      <th className="px-4 py-3">Category</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => {
                      const hasDimensions = !!(item.dimensions && item.dimensions.length > 0);
                      const isExpanded = expandedRows.has(item.id);

                      return (
                        <React.Fragment key={item.id}>
                          <tr
                            className={`border-b border-gray-100 ${
                              item.is_hidden ? 'opacity-40 line-through' : ''
                            }`}
                          >
                            <td className="px-4 py-3 text-gray-600">{item.row_number}</td>
                            <td className="px-4 py-3">
                              <Badge
                                variant={
                                  item.type === 'boq_item'
                                    ? 'default'
                                    : item.type === 'section_description'
                                      ? 'warning'
                                      : 'info'
                                }
                              >
                                {item.type === 'boq_item'
                                  ? 'BOQ Item'
                                  : item.type === 'section_description'
                                    ? 'Section'
                                    : 'Doc Info'}
                              </Badge>
                            </td>
                            <td className="max-w-xs truncate px-4 py-3 text-gray-900">
                              {item.description || '\u2014'}
                            </td>
                            <td className="px-4 py-3 text-gray-600">
                              <span className="inline-flex items-center gap-1">
                                {item.quantity != null ? item.quantity : '\u2014'}
                                {hasDimensions && (
                                  <button
                                    onClick={() => toggleRow(item.id)}
                                    className="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                                    title={isExpanded ? 'Collapse dimensions' : 'Expand dimensions'}
                                  >
                                    {isExpanded ? (
                                      <ChevronUp className="h-3.5 w-3.5" />
                                    ) : (
                                      <ChevronDown className="h-3.5 w-3.5" />
                                    )}
                                  </button>
                                )}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-gray-600">{item.unit || '\u2014'}</td>
                            <td className="px-4 py-3">
                              {item.category ? (
                                <Badge variant={CATEGORY_VARIANTS[item.category] ?? 'default'}>
                                  {CATEGORY_LABELS[item.category] ?? item.category}
                                </Badge>
                              ) : (
                                <span className="text-gray-400">{'\u2014'}</span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant={item.is_valid ? 'success' : 'danger'}>
                                {item.is_valid ? 'Valid' : 'Invalid'}
                              </Badge>
                            </td>
                            <td className="px-4 py-3">
                              <button
                                onClick={() => handleToggleVisibility(item)}
                                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                                title={item.is_hidden ? 'Show item' : 'Hide item'}
                              >
                                {item.is_hidden ? (
                                  <EyeOff className="h-4 w-4" />
                                ) : (
                                  <Eye className="h-4 w-4" />
                                )}
                              </button>
                            </td>
                          </tr>
                          {hasDimensions && isExpanded && (
                            <tr className="border-b border-gray-100 bg-blue-50/40">
                              <td colSpan={8} className="px-8 py-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-xs font-medium text-gray-500">Dimensions:</span>
                                  {item.dimensions!.map((dim) => (
                                    <span
                                      key={dim.name}
                                      className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800"
                                    >
                                      {dim.name}: {dim.quantity ?? 0}
                                      {dim.building_count != null && ` (${dim.building_count} bldgs)`}
                                    </span>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
                  <span className="text-sm text-gray-500">
                    Page {page} of {totalPages} ({total} items)
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => fetchItems(page - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => fetchItems(page + 1)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
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
