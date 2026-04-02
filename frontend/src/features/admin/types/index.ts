export interface Tenant {
  id: string;
  name: string;
  slug: string;
  status: string;
  user_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface TenantListResponse {
  items: Tenant[];
  total: number;
}

export interface CreateTenantRequest {
  name: string;
  slug: string;
  admin_email: string;
}

export interface CreateTenantResponse {
  tenant: Tenant;
  admin_user: {
    id: string;
    email: string;
    role: string;
    is_active: boolean;
  };
}
