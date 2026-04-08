export interface Project {
  id: string;
  tenant_id: string;
  owner_user_id: string;
  project_name: string;
  client_id?: string | null;
  client_name?: string | null;
  country: string;
  city: string;
  due_date: string;
  panel_family: string | null;
  status: 'IN_PROGRESS' | 'IN_REVIEW' | 'COMPLETED';
  created_at: string | null;
  updated_at: string | null;
}

export interface ProjectAdmin {
  id: string;
  project_name: string;
  client_name?: string | null;
  status: 'IN_PROGRESS' | 'IN_REVIEW' | 'COMPLETED';
  created_at: string | null;
  created_by_name: string | null;
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface ProjectListResponse {
  data: Project[];
  pagination: PaginationMeta;
}

export interface ProjectAdminListResponse {
  data: ProjectAdmin[];
  pagination: PaginationMeta;
}

export interface CreateProjectRequest {
  project_name: string;
  client_id: string;
  country: string;
  city: string;
  due_date: string;
}

export interface UpdateProjectRequest {
  project_name?: string;
  client_id?: string;
  country?: string;
  city?: string;
  due_date?: string;
}
