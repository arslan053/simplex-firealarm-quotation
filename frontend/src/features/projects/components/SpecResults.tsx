import { useCallback, useEffect, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';

import type { SpecBlock } from '../types/spec';
import { specApi } from '../api/spec.api';
import { Button } from '@/shared/ui/Button';
import { Card } from '@/shared/ui/Card';

interface SpecResultsProps {
  projectId: string;
  documentId: string;
  refreshKey: number;
}

const BLOCKS_PER_PAGE = 100;

const STYLE_COLORS: Record<string, string> = {
  Heading1: 'bg-indigo-100 text-indigo-800',
  Heading2: 'bg-blue-100 text-blue-800',
  Heading3: 'bg-cyan-100 text-cyan-800',
  Heading4: 'bg-teal-100 text-teal-800',
  Heading5: 'bg-emerald-100 text-emerald-800',
  Heading6: 'bg-green-100 text-green-800',
  paragraph: 'bg-gray-100 text-gray-700',
  list_item: 'bg-yellow-100 text-yellow-800',
};

export function SpecResults({
  projectId,
  documentId,
  refreshKey,
}: SpecResultsProps) {
  const [blocks, setBlocks] = useState<SpecBlock[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // Collapsible page sections
  const [collapsedPages, setCollapsedPages] = useState<Set<number>>(new Set());

  const fetchBlocks = useCallback(
    async (pg: number) => {
      if (!documentId) return;
      setLoading(true);
      try {
        const { data } = await specApi.getBlocks(
          projectId,
          documentId,
          pg,
          BLOCKS_PER_PAGE,
        );
        console.log('data camedddd', data)
        setBlocks(data.data);
        setTotal(data.pagination.total);
        setTotalPages(data.pagination.total_pages);
      } catch {
        // Silently handle — blocks may not exist yet
      } finally {
        setLoading(false);
      }
    },
    [projectId, documentId],
  );

  useEffect(() => {
    fetchBlocks(page);
  }, [fetchBlocks, page, refreshKey]);

  const togglePageCollapse = (pageNo: number) => {
    setCollapsedPages((prev) => {
      const next = new Set(prev);
      if (next.has(pageNo)) {
        next.delete(pageNo);
      } else {
        next.add(pageNo);
      }
      return next;
    });
  };

  if (blocks.length === 0 && !loading) return null;

  // Group blocks by page_no
  const pageGroups = new Map<number, SpecBlock[]>();
  for (const block of blocks) {
    const existing = pageGroups.get(block.page_no) || [];
    existing.push(block);
    pageGroups.set(block.page_no, existing);
  }
  const sortedPageNos = [...pageGroups.keys()].sort((a, b) => a - b);

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          Specification Blocks ({total} total)
        </h3>
      </div>

      {loading && blocks.length === 0 ? (
        <div className="py-8 text-center text-sm text-gray-500">
          Loading blocks...
        </div>
      ) : (
        <div className="space-y-3">
          {sortedPageNos.map((pageNo) => {
            const pageBlocks = pageGroups.get(pageNo)!;
            const isCollapsed = collapsedPages.has(pageNo);

            return (
              <div
                key={pageNo}
                className="rounded-lg border border-gray-200"
              >
                <button
                  onClick={() => togglePageCollapse(pageNo)}
                  className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  <span className="flex items-center gap-2">
                    {isCollapsed ? (
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    )}
                    Page {pageNo}
                    <span className="text-xs font-normal text-gray-400">
                      ({pageBlocks.length} block
                      {pageBlocks.length !== 1 ? 's' : ''})
                    </span>
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="border-t border-gray-100 px-4 py-2">
                    <div className="space-y-1">
                      {pageBlocks.map((block) => {
                        const indent =
                          block.level != null ? block.level * 16 : 0;
                        const styleClass =
                          STYLE_COLORS[block.style] ||
                          'bg-gray-100 text-gray-700';

                        return (
                          <div
                            key={block.id}
                            className="flex items-start gap-2 py-1"
                            style={{ paddingLeft: `${indent}px` }}
                          >
                            <span
                              className={`mt-0.5 inline-flex flex-shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${styleClass}`}
                            >
                              {block.style}
                            </span>
                            <span className="min-w-0 flex-1 text-sm text-gray-800">
                              {block.content}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between border-t border-gray-200 pt-3">
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
