import { useEffect, useState } from 'react';
import { FileText, Eye, Loader2 } from 'lucide-react';

import { documentsApi } from '../api/documents.api';
import type { DocumentResponse } from '../types/boq';
import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';

interface Props {
  projectId: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectDocuments({ projectId }: Props) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewingId, setViewingId] = useState<string | null>(null);

  useEffect(() => {
    documentsApi
      .listAll(projectId)
      .then(({ data }) => setDocuments(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleView = async (doc: DocumentResponse) => {
    setViewingId(doc.id);
    // Open window immediately (before await) to preserve user-gesture context
    // and avoid browser popup blockers
    const newWindow = window.open('about:blank', '_blank');
    try {
      const { data } = await documentsApi.getViewUrl(projectId, doc.id);
      if (newWindow) {
        newWindow.location.href = data.url;
      }
    } catch {
      if (newWindow) newWindow.close();
    } finally {
      setViewingId(null);
    }
  };

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center py-8 text-gray-400">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading documents...
        </div>
      </Card>
    );
  }

  if (documents.length === 0) return null;

  return (
    <Card>
      <div className="mb-4 flex items-center gap-2">
        <FileText className="h-5 w-5 text-indigo-500" />
        <h3 className="text-lg font-semibold text-gray-900">Project Documents</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase text-gray-400">
              <th className="pb-2 pr-4">File Name</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Size</th>
              <th className="pb-2 pr-4">Uploaded</th>
              <th className="pb-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td className="py-2.5 pr-4 font-medium text-gray-900">
                  {doc.original_file_name}
                </td>
                <td className="py-2.5 pr-4">
                  <Badge variant={doc.type === 'SPEC' ? 'warning' : 'default'}>
                    {doc.type}
                  </Badge>
                </td>
                <td className="py-2.5 pr-4 text-gray-500">
                  {formatFileSize(doc.file_size)}
                </td>
                <td className="py-2.5 pr-4 text-gray-500">
                  {doc.created_at
                    ? new Date(doc.created_at).toLocaleDateString()
                    : '\u2014'}
                </td>
                <td className="py-2.5 text-right">
                  <button
                    onClick={() => handleView(doc)}
                    disabled={viewingId === doc.id}
                    className="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50"
                  >
                    {viewingId === doc.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
