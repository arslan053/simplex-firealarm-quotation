import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FileText,
  Image,
  Trash2,
  Upload,
  Paperclip,
  RefreshCw,
  X,
} from 'lucide-react';

import { settingsApi } from '../api/settings.api';
import type { CompanySettings } from '../types';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

export function GeneralSettingsPage() {
  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<'letterhead' | 'signature' | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<'letterhead' | 'signature' | null>(null);

  // Staged files — selected but not yet uploaded
  const [stagedLetterhead, setStagedLetterhead] = useState<File | null>(null);
  const [stagedSignature, setStagedSignature] = useState<File | null>(null);

  const [signatoryName, setSignatoryName] = useState('');
  const [companyPhone, setCompanyPhone] = useState('');

  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const letterheadRef = useRef<HTMLInputElement>(null);
  const signatureRef = useRef<HTMLInputElement>(null);

  const fetchSettings = useCallback(async () => {
    try {
      const { data } = await settingsApi.getCompanySettings();
      setSettings(data);
      setSignatoryName(data.signatory_name || '');
      setCompanyPhone(data.company_phone || '');
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const clearMessages = () => {
    setSuccessMsg('');
    setErrorMsg('');
  };

  // Stage file selection (don't upload yet)
  const handleLetterheadSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    clearMessages();
    setStagedLetterhead(file);
    if (letterheadRef.current) letterheadRef.current.value = '';
  };

  const handleSignatureSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    clearMessages();
    setStagedSignature(file);
    if (signatureRef.current) signatureRef.current.value = '';
  };

  // Actually upload the staged file
  const handleLetterheadUpload = async () => {
    if (!stagedLetterhead) return;
    clearMessages();
    setUploading('letterhead');
    try {
      const { data } = await settingsApi.uploadLetterhead(stagedLetterhead);
      setSettings(data);
      setStagedLetterhead(null);
      setSuccessMsg('Letterhead uploaded successfully.');
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setUploading(null);
    }
  };

  const handleSignatureUpload = async () => {
    if (!stagedSignature) return;
    clearMessages();
    setUploading('signature');
    try {
      const { data } = await settingsApi.uploadSignature(stagedSignature);
      setSettings(data);
      setStagedSignature(null);
      setSuccessMsg('Signature uploaded successfully.');
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setUploading(null);
    }
  };

  const handleDeleteLetterhead = async () => {
    if (!window.confirm('Remove the company letterhead? Quotations will use the default layout.')) return;
    clearMessages();
    setDeleting('letterhead');
    try {
      const { data } = await settingsApi.deleteLetterhead();
      setSettings(data);
      setSuccessMsg('Letterhead removed.');
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setDeleting(null);
    }
  };

  const handleDeleteSignature = async () => {
    if (!window.confirm('Remove the custom signature?')) return;
    clearMessages();
    setDeleting('signature');
    try {
      const { data } = await settingsApi.deleteSignature();
      setSettings(data);
      setSuccessMsg('Signature removed.');
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setDeleting(null);
    }
  };

  const handleSaveText = async () => {
    clearMessages();
    setSaving(true);
    try {
      const { data } = await settingsApi.updateTextSettings({
        signatory_name: signatoryName || undefined,
        company_phone: companyPhone || undefined,
      });
      setSettings(data);
      setSuccessMsg('Settings saved successfully.');
    } catch (err) {
      setErrorMsg(normalizeError(err).message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="py-12 text-center text-gray-500">Loading settings...</div>;
  }

  return (
    <div className="space-y-6">
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

      {/* Letterhead Section */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
              <FileText className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Company Letterhead</h3>
              <p className="text-sm text-gray-500">
                Upload your company letterhead (.docx). This will be used as the base document for all generated quotations.
              </p>
            </div>
          </div>

          <input
            ref={letterheadRef}
            type="file"
            accept=".docx"
            className="hidden"
            onChange={handleLetterheadSelect}
          />

          {/* Already uploaded — show current file with Replace / Remove */}
          {settings?.letterhead_uploaded && !stagedLetterhead && (
            <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
              <Paperclip className="h-5 w-5 text-gray-500" />
              <span className="flex-1 text-sm font-medium text-gray-700">
                {settings.letterhead_filename ?? ''}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => letterheadRef.current?.click()}
              >
                <RefreshCw className="mr-1 h-3 w-3" />
                Replace
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteLetterhead}
                isLoading={deleting === 'letterhead'}
              >
                <Trash2 className="mr-1 h-3 w-3" />
                Remove
              </Button>
            </div>
          )}

          {/* Staged file selected — show filename + Upload & Save + Cancel */}
          {stagedLetterhead && (
            <div className="flex items-center gap-3 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3">
              <FileText className="h-5 w-5 text-indigo-600" />
              <span className="flex-1 text-sm font-medium text-indigo-800">
                {stagedLetterhead.name}
              </span>
              <Button
                size="sm"
                onClick={handleLetterheadUpload}
                isLoading={uploading === 'letterhead'}
              >
                <Upload className="mr-1 h-3 w-3" />
                Upload & Save
              </Button>
              <button
                onClick={() => setStagedLetterhead(null)}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Nothing uploaded and nothing staged — show Select File button */}
          {!settings?.letterhead_uploaded && !stagedLetterhead && (
            <Button
              variant="outline"
              onClick={() => letterheadRef.current?.click()}
            >
              <Upload className="mr-2 h-4 w-4" />
              Select Letterhead
            </Button>
          )}
        </div>
      </Card>

      {/* Signature Section */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
              <Image className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Quotation Signature</h3>
              <p className="text-sm text-gray-500">
                Upload a signature image (.png, .jpg) and configure the signatory details for quotations.
              </p>
            </div>
          </div>

          <input
            ref={signatureRef}
            type="file"
            accept=".png,.jpg,.jpeg"
            className="hidden"
            onChange={handleSignatureSelect}
          />

          {/* Already uploaded — show current file with Replace / Remove */}
          {settings?.signature_uploaded && !stagedSignature && (
            <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
              <Paperclip className="h-5 w-5 text-gray-500" />
              <span className="flex-1 text-sm font-medium text-gray-700">
                {settings.signature_filename}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => signatureRef.current?.click()}
              >
                <RefreshCw className="mr-1 h-3 w-3" />
                Replace
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteSignature}
                isLoading={deleting === 'signature'}
              >
                <Trash2 className="mr-1 h-3 w-3" />
                Remove
              </Button>
            </div>
          )}

          {/* Staged file selected — show filename + Upload & Save + Cancel */}
          {stagedSignature && (
            <div className="flex items-center gap-3 rounded-lg border border-purple-200 bg-purple-50 px-4 py-3">
              <Image className="h-5 w-5 text-purple-600" />
              <span className="flex-1 text-sm font-medium text-purple-800">
                {stagedSignature.name}
              </span>
              <Button
                size="sm"
                onClick={handleSignatureUpload}
                isLoading={uploading === 'signature'}
              >
                <Upload className="mr-1 h-3 w-3" />
                Upload & Save
              </Button>
              <button
                onClick={() => setStagedSignature(null)}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Nothing uploaded and nothing staged — show Select File button */}
          {!settings?.signature_uploaded && !stagedSignature && (
            <Button
              variant="outline"
              onClick={() => signatureRef.current?.click()}
            >
              <Upload className="mr-2 h-4 w-4" />
              Select Signature
            </Button>
          )}

          <div className="border-t pt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Signatory Name"
                placeholder="e.g. Ahmad Al-Rashid"
                value={signatoryName}
                onChange={(e) => setSignatoryName(e.target.value)}
              />
              <Input
                label="Company Phone"
                placeholder="e.g. +966 11 222 3344"
                value={companyPhone}
                onChange={(e) => setCompanyPhone(e.target.value)}
              />
            </div>
            <div className="mt-4">
              <Button onClick={handleSaveText} isLoading={saving}>
                Save
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
