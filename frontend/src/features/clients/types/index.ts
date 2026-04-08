export interface Client {
  id: string;
  tenant_id: string;
  name: string;
  company_name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ClientSearchItem {
  id: string;
  name: string;
  company_name: string;
}

export interface ClientListResponse {
  data: Client[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}
