import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Upload, Search, Save, DollarSign, CheckCircle, Package, AlertTriangle, X, ArrowRight } from 'lucide-react';

import { tenantPricingApi } from '../api/tenantPricing.api';
import type { TenantProductPrice, TemplateValidationError } from '../types';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

interface PriceChange {
  code: string;
  description: string;
  oldPrice: number;
  newPrice: number;
  currency: string;
}

export function PriceListPage() {
  const [items, setItems] = useState<TenantProductPrice[]>([]);
  const [total, setTotal] = useState(0);
  const [pricesSet, setPricesSet] = useState(0);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');

  // Track edited prices: product_id -> new price
  const [editedPrices, setEditedPrices] = useState<Record<string, number>>({});
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [uploadErrors, setUploadErrors] = useState<TemplateValidationError[]>([]);
  const [showConfirm, setShowConfirm] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>();

  const fetchList = useCallback(async (searchVal?: string, categoryVal?: string) => {
    try {
      const params: { search?: string; category?: string } = {};
      if (searchVal) params.search = searchVal;
      if (categoryVal) params.category = categoryVal;
      const { data } = await tenantPricingApi.getList(params);
      setItems(data.items);
      setTotal(data.total);
      setPricesSet(data.prices_set);
    } catch (err) {
      console.error('Failed to load price list', err);
      setErrorMsg(normalizeError(err).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const { data } = await tenantPricingApi.getCategories();
      setCategories(data.categories);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchList();
    fetchCategories();
  }, [fetchList, fetchCategories]);

  const handleSearchChange = (value: string) => {
    setSearch(value);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      fetchList(value, category);
    }, 400);
  };

  const handleCategoryChange = (value: string) => {
    setCategory(value);
    fetchList(search, value);
  };

  const handlePriceChange = (productId: string, value: string) => {
    const num = parseFloat(value);
    if (value === '' || isNaN(num)) {
      setEditedPrices((prev) => {
        const next = { ...prev };
        delete next[productId];
        return next;
      });
      return;
    }
    setEditedPrices((prev) => ({ ...prev, [productId]: num }));
  };

  const getChangedProducts = (): PriceChange[] => {
    const itemMap = new Map(items.map((i) => [i.product_id, i]));
    return Object.entries(editedPrices)
      .map(([productId, newPrice]) => {
        const item = itemMap.get(productId);
        if (!item) return null;
        return {
          code: item.code,
          description: item.description,
          oldPrice: item.price,
          newPrice,
          currency: item.currency,
        };
      })
      .filter((c): c is PriceChange => c !== null);
  };

  const handleSaveClick = () => {
    if (Object.keys(editedPrices).length === 0) return;
    setShowConfirm(true);
  };

  const handleConfirmSave = async () => {
    setShowConfirm(false);
    const entries = Object.entries(editedPrices);
    if (entries.length === 0) return;

    setSaving(true);
    setSuccessMsg('');
    setErrorMsg('');
    setUploadErrors([]);

    try {
      const payload = entries.map(([product_id, price]) => ({ product_id, price }));
      const { data } = await tenantPricingApi.updatePrices(payload);
      setSuccessMsg(`${data.updated} price${data.updated !== 1 ? 's' : ''} updated successfully.`);
      setEditedPrices({});
      fetchList(search, category);
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    try {
      const { data } = await tenantPricingApi.downloadTemplate();
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'price_list_template.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setSuccessMsg('');
    setErrorMsg('');
    setUploadErrors([]);

    try {
      const { data } = await tenantPricingApi.uploadTemplate(file);
      if (data.errors.length > 0) {
        setUploadErrors(data.errors);
        if (data.updated > 0) {
          setSuccessMsg(`${data.updated} price${data.updated !== 1 ? 's' : ''} updated. ${data.errors.length} row${data.errors.length !== 1 ? 's' : ''} had errors.`);
        } else {
          setErrorMsg(`Upload failed — ${data.errors.length} validation error${data.errors.length !== 1 ? 's' : ''}.`);
        }
      } else {
        setSuccessMsg(`${data.updated} price${data.updated !== 1 ? 's' : ''} updated from template.`);
      }
      setEditedPrices({});
      fetchList(search, category);
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const hasEdits = Object.keys(editedPrices).length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Price List</h1>
          <p className="text-sm text-gray-500">
            Manage product prices for your company
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={handleDownload}>
            <Download className="mr-2 h-4 w-4" />
            Template
          </Button>
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            isLoading={uploading}
          >
            <Upload className="mr-2 h-4 w-4" />
            Upload
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={handleUpload}
          />
          {hasEdits && (
            <Button onClick={handleSaveClick} isLoading={saving}>
              <Save className="mr-2 h-4 w-4" />
              Save Changes ({Object.keys(editedPrices).length})
            </Button>
          )}
        </div>
      </div>

      {/* Messages */}
      {successMsg && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700">
          {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {errorMsg}
        </div>
      )}
      {uploadErrors.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <p className="mb-2 text-sm font-medium text-amber-800">Upload Validation Errors:</p>
          <ul className="space-y-1 text-sm text-amber-700">
            {uploadErrors.map((e, i) => (
              <li key={i}>
                Row {e.row}: {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
              <Package className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Products</p>
              <p className="text-xl font-semibold text-gray-900">{total}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
              <CheckCircle className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Prices Set</p>
              <p className="text-xl font-semibold text-gray-900">{pricesSet}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
              <DollarSign className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Pending Changes</p>
              <p className="text-xl font-semibold text-gray-900">
                {Object.keys(editedPrices).length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by code or description..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="block w-full rounded-lg border border-gray-300 py-2 pl-10 pr-3 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <select
          value={category}
          onChange={(e) => handleCategoryChange(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <Card className="overflow-hidden p-0">
        {loading ? (
          <div className="py-12 text-center text-gray-500">Loading price list...</div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            {search || category ? 'No products match your filters.' : 'No products found.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50">
                <tr>
                  <th className="px-6 py-3 font-medium text-gray-500">Code</th>
                  <th className="px-6 py-3 font-medium text-gray-500">Description</th>
                  <th className="px-6 py-3 font-medium text-gray-500">Category</th>
                  <th className="px-6 py-3 font-medium text-gray-500">Currency</th>
                  <th className="w-40 px-6 py-3 font-medium text-gray-500">Price</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((item) => {
                  const isEdited = item.product_id in editedPrices;
                  const displayPrice = isEdited
                    ? editedPrices[item.product_id]
                    : item.price;

                  return (
                    <tr
                      key={item.product_id}
                      className={isEdited ? 'bg-indigo-50/50' : 'hover:bg-gray-50'}
                    >
                      <td className="whitespace-nowrap px-6 py-3 font-mono text-xs text-gray-700">
                        {item.code}
                      </td>
                      <td className="max-w-xs truncate px-6 py-3 text-gray-900" title={item.description}>
                        {item.description}
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-gray-500">
                        {item.category.replace(/_/g, ' ')}
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-gray-500">
                        {item.currency}
                      </td>
                      <td className="px-6 py-3">
                        <input
                          type="number"
                          step="0.001"
                          min="0"
                          value={displayPrice}
                          onChange={(e) =>
                            handlePriceChange(item.product_id, e.target.value)
                          }
                          className={`w-32 rounded border px-2 py-1 text-right text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${
                            isEdited
                              ? 'border-indigo-300 bg-white'
                              : 'border-gray-300'
                          }`}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Sticky save bar when there are edits */}
      {hasEdits && (
        <div className="fixed bottom-0 left-0 right-0 z-20 border-t bg-white px-6 py-3 shadow-lg">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <p className="text-sm text-gray-600">
              {Object.keys(editedPrices).length} unsaved change{Object.keys(editedPrices).length !== 1 ? 's' : ''}
            </p>
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditedPrices({})}
              >
                Discard
              </Button>
              <Button size="sm" onClick={handleSaveClick} isLoading={saving}>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-lg rounded-lg bg-white shadow-xl">
            {/* Header */}
            <div className="flex items-center gap-3 border-b px-6 py-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-gray-900">Confirm Price Changes</h2>
                <p className="text-sm text-gray-500">
                  {getChangedProducts().length} product{getChangedProducts().length !== 1 ? 's' : ''} will be updated
                </p>
              </div>
              <button onClick={() => setShowConfirm(false)}>
                <X className="h-5 w-5 text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            {/* Changes list */}
            <div className="max-h-72 overflow-y-auto px-6 py-4">
              <div className="space-y-3">
                {getChangedProducts().map((change) => (
                  <div
                    key={change.code}
                    className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-xs text-gray-500">{change.code}</p>
                        <p className="truncate text-sm font-medium text-gray-900">{change.description}</p>
                      </div>
                      <div className="ml-4 flex items-center gap-2 text-sm">
                        <span className="text-gray-400 line-through">
                          {change.oldPrice.toFixed(3)}
                        </span>
                        <ArrowRight className="h-3 w-3 text-gray-400" />
                        <span className="font-semibold text-indigo-600">
                          {change.newPrice.toFixed(3)}
                        </span>
                        <span className="text-xs text-gray-400">{change.currency}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Impact notice */}
            <div className="border-t bg-amber-50 px-6 py-3">
              <p className="text-xs text-amber-800">
                These changes will take effect immediately. All future quotations for your company will use the updated prices. Existing quotations will not be affected.
              </p>
            </div>

            {/* Actions */}
            <div className="flex gap-3 border-t px-6 py-4">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                className="flex-1"
                onClick={handleConfirmSave}
                isLoading={saving}
              >
                Yes, Update Prices
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
