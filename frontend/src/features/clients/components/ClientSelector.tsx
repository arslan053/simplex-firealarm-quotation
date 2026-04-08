import { useEffect, useRef, useState } from 'react';
import { Plus, Search, ChevronDown } from 'lucide-react';

import { clientsApi } from '../api/clients.api';
import type { Client, ClientSearchItem } from '../types';
import { CreateClientModal } from './CreateClientModal';

interface ClientSelectorProps {
  value: string | null;
  onChange: (clientId: string, client: ClientSearchItem) => void;
  error?: string;
}

export function ClientSelector({ value, onChange, error }: ClientSelectorProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ClientSearchItem[]>([]);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<ClientSearchItem | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Load initial selection if value is set but selected is not
  useEffect(() => {
    if (value && !selected) {
      clientsApi.get(value).then(({ data }) => {
        setSelected({ id: data.id, name: data.name, company_name: data.company_name });
      }).catch(() => {});
    }
  }, [value, selected]);

  // Search on query change
  useEffect(() => {
    if (!open) return;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      clientsApi.search(query).then(({ data }) => {
        setResults(data);
      }).catch(() => {}).finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query, open]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleSelect = (client: ClientSearchItem) => {
    setSelected(client);
    onChange(client.id, client);
    setOpen(false);
    setQuery('');
  };

  const handleCreated = (client: Client) => {
    const item: ClientSearchItem = { id: client.id, name: client.name, company_name: client.company_name };
    setSelected(item);
    onChange(client.id, item);
    setShowCreateModal(false);
    setOpen(false);
    setQuery('');
  };

  return (
    <div className="w-full" ref={containerRef}>
      <label className="mb-1 block text-sm font-medium text-gray-700">Client</label>

      {/* Trigger */}
      <button
        type="button"
        onClick={() => {
          setOpen(!open);
          setTimeout(() => inputRef.current?.focus(), 50);
        }}
        className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm shadow-sm transition-colors ${
          error
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
            : open
              ? 'border-indigo-500 ring-1 ring-indigo-500'
              : 'border-gray-300'
        }`}
      >
        <span className={selected ? 'text-gray-900' : 'text-gray-400'}>
          {selected ? `${selected.company_name} — ${selected.name}` : 'Select a client...'}
        </span>
        <ChevronDown className="h-4 w-4 text-gray-400" />
      </button>

      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}

      {/* Dropdown */}
      {open && (
        <div className="absolute z-20 mt-1 w-full max-w-md rounded-lg border border-gray-200 bg-white shadow-lg">
          {/* Search input */}
          <div className="flex items-center gap-2 border-b border-gray-100 px-3 py-2">
            <Search className="h-4 w-4 text-gray-400" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search clients..."
              className="w-full bg-transparent text-sm outline-none placeholder:text-gray-400"
            />
          </div>

          {/* Results */}
          <div className="max-h-48 overflow-y-auto">
            {loading && (
              <div className="px-3 py-2 text-sm text-gray-400">Searching...</div>
            )}
            {!loading && results.length === 0 && (
              <div className="px-3 py-2 text-sm text-gray-400">No clients found</div>
            )}
            {!loading &&
              results.map((client) => (
                <button
                  key={client.id}
                  type="button"
                  onClick={() => handleSelect(client)}
                  className={`flex w-full flex-col px-3 py-2 text-left hover:bg-gray-50 ${
                    value === client.id ? 'bg-indigo-50' : ''
                  }`}
                >
                  <span className="text-sm font-medium text-gray-900">
                    {client.company_name}
                  </span>
                  <span className="text-xs text-gray-500">{client.name}</span>
                </button>
              ))}
          </div>

          {/* Create new */}
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="flex w-full items-center gap-2 border-t border-gray-100 px-3 py-2.5 text-sm font-medium text-indigo-600 hover:bg-indigo-50"
          >
            <Plus className="h-4 w-4" />
            Create New Client
          </button>
        </div>
      )}

      {showCreateModal && (
        <CreateClientModal
          onClose={() => setShowCreateModal(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
