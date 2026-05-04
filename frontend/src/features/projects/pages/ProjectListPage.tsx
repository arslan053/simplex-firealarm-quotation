import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderOpen, Plus, Search, ChevronLeft, ChevronRight } from 'lucide-react';

import { projectsApi } from '../api/projects.api';
import type { Project, ProjectAdmin, PaginationMeta } from '../types';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Badge } from '@/shared/ui/Badge';
import { cn } from '@/shared/utils/cn';

const statusVariant: Record<string, 'default' | 'warning' | 'success'> = {
  IN_PROGRESS: 'default',
  IN_REVIEW: 'warning',
  COMPLETED: 'success',
};

const statusLabel: Record<string, string> = {
  IN_PROGRESS: 'In Progress',
  IN_REVIEW: 'In Review',
  COMPLETED: 'Completed',
};

type Tab = 'my' | 'company';

export function ProjectListPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin';

  const [activeTab, setActiveTab] = useState<Tab>('my');
  const [projects, setProjects] = useState<(Project | ProjectAdmin)[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta>({
    page: 1, limit: 10, total: 0, total_pages: 0,
  });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const fetchProjects = useCallback(async (page: number, searchTerm: string, tab: Tab) => {
    setLoading(true);
    try {
      const view = isAdmin ? (tab === 'my' ? 'my' : 'all') : undefined;
      const { data } = await projectsApi.list({
        page,
        limit: 10,
        search: searchTerm || undefined,
        view,
      });
      setProjects(data.data);
      setPagination(data.pagination);
    } catch (err) {
      console.error('Failed to load projects', err);
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    fetchProjects(1, '', activeTab);
  }, [fetchProjects, activeTab]);

  const handleSearch = () => {
    setSearch(searchInput);
    fetchProjects(1, searchInput, activeTab);
  };

  const handlePageChange = (newPage: number) => {
    fetchProjects(newPage, search, activeTab);
  };

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    setSearch('');
    setSearchInput('');
  };

  // Determine if we're showing full-field (owner) view or restricted (admin company) view
  const isOwnerView = !isAdmin || activeTab === 'my';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-sm text-gray-500">
            {isAdmin
              ? activeTab === 'my' ? 'Projects you created' : 'All company projects'
              : 'Your projects'}
          </p>
        </div>
        <Button onClick={() => navigate('/projects/new')}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {/* Admin Tabs */}
      {isAdmin && (
        <div className="flex gap-1 rounded-lg bg-gray-100 p-1">
          <button
            onClick={() => handleTabChange('my')}
            className={cn(
              'flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors',
              activeTab === 'my'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700',
            )}
          >
            My Projects
          </button>
          <button
            onClick={() => handleTabChange('company')}
            className={cn(
              'flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors',
              activeTab === 'company'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700',
            )}
          >
            Company Projects
          </button>
        </div>
      )}

      {/* Search */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by project or client name..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <Button variant="outline" onClick={handleSearch}>
          Search
        </Button>
      </div>

      {/* Table */}
      <Card className="overflow-hidden p-0">
        {loading ? (
          <div className="py-12 text-center text-gray-500">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="py-12 text-center">
            <FolderOpen className="mx-auto mb-3 h-10 w-10 text-gray-300" />
            <p className="text-gray-500">
              {search
                ? 'No projects match your search.'
                : isAdmin && activeTab === 'company'
                  ? 'No projects in this company yet.'
                  : 'No projects yet.'}
            </p>
            {isOwnerView && !search && (
              <Button className="mt-4" size="sm" onClick={() => navigate('/projects/new')}>
                Create your first project
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50">
                <tr>
                  <th className="px-4 py-3 font-medium text-gray-500 sm:px-6">Project Name</th>
                  <th className="px-4 py-3 font-medium text-gray-500 sm:px-6">Client</th>
                  <th className="hidden px-4 py-3 font-medium text-gray-500 sm:table-cell sm:px-6">Status</th>
                  {!isOwnerView && (
                    <th className="hidden px-4 py-3 font-medium text-gray-500 md:table-cell md:px-6">Created By</th>
                  )}
                  {isOwnerView && (
                    <>
                      <th className="hidden px-4 py-3 font-medium text-gray-500 md:table-cell md:px-6">Country</th>
                      <th className="hidden px-4 py-3 font-medium text-gray-500 lg:table-cell lg:px-6">Due Date</th>
                    </>
                  )}
                  <th className="hidden px-4 py-3 font-medium text-gray-500 sm:table-cell sm:px-6">Created</th>
                  <th className="px-4 py-3 font-medium text-gray-500 sm:px-6"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {projects.map((p) => (
                  <tr
                    key={p.id}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => navigate(`/projects/${p.id}/setup`)}
                  >
                    <td className="px-4 py-4 font-medium text-gray-900 sm:px-6">
                      <span className="line-clamp-1">{p.project_name}</span>
                      {/* Mobile: show status inline */}
                      <div className="mt-1 sm:hidden">
                        <Badge variant={statusVariant[p.status] || 'default'}>
                          {statusLabel[p.status] || p.status}
                        </Badge>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-600 sm:px-6">
                      <span className="line-clamp-1">{p.client_name || '\u2014'}</span>
                    </td>
                    <td className="hidden px-4 py-4 sm:table-cell sm:px-6">
                      <Badge variant={statusVariant[p.status] || 'default'}>
                        {statusLabel[p.status] || p.status}
                      </Badge>
                    </td>
                    {!isOwnerView && (
                      <td className="hidden px-4 py-4 text-gray-500 md:table-cell md:px-6">
                        {(p as ProjectAdmin).created_by_name || '—'}
                      </td>
                    )}
                    {isOwnerView && (
                      <>
                        <td className="hidden px-4 py-4 text-gray-600 md:table-cell md:px-6">
                          {(p as Project).country}
                        </td>
                        <td className="hidden px-4 py-4 text-gray-500 lg:table-cell lg:px-6">
                          {(p as Project).due_date}
                        </td>
                      </>
                    )}
                    <td className="hidden px-4 py-4 text-gray-500 sm:table-cell sm:px-6">
                      {p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-4 sm:px-6">
                      <button
                        className="text-xs text-indigo-600 hover:text-indigo-800"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/projects/${p.id}/setup`);
                        }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Pagination */}
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Page {pagination.page} of {pagination.total_pages} ({pagination.total} projects)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page <= 1}
              onClick={() => handlePageChange(pagination.page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => handlePageChange(pagination.page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
