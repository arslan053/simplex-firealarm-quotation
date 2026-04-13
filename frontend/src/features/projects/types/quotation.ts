export interface InclusionQuestion {
  key: string;
  text: string;
  mode: 'ask_user' | 'auto_detect';
  value: boolean | null;
  group: string | null;
}

export interface GenerateQuotationRequest {
  client_name: string;
  client_address: string;
  subject?: string;
  service_option: number;
  margin_percent: number;
  payment_terms_text: string;
  inclusion_answers?: Record<string, boolean>;
}

export interface QuotationResponse {
  id: string;
  project_id: string;
  reference_number: string;
  client_name: string;
  client_address: string;
  subject?: string | null;
  service_option: number;
  margin_percent: number;
  payment_terms_text?: string | null;
  inclusion_answers?: Record<string, boolean>;
  subtotal_sar: number;
  vat_sar: number;
  grand_total_sar: number;
  original_file_name: string;
  created_at: string;
  updated_at: string;
}

export interface QuotationDownloadResponse {
  url: string;
  file_name: string;
}
