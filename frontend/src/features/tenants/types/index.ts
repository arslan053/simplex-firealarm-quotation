export interface TenantInfo {
  id: string;
  slug: string;
  name: string;
  status: string;
  settings_json: Record<string, unknown> | null;
}

export interface TenantResolveResponse {
  id?: string;
  slug?: string;
  name?: string;
  status?: string;
  settings_json?: Record<string, unknown> | null;
  is_admin_domain?: boolean;
}

export interface TenantContext {
  tenant: TenantInfo | null;
  isAdminDomain: boolean;
  isLoading: boolean;
  error: string | null;
}
