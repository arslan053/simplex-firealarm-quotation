export interface GenerateQuotationRequest {
  client_name: string;
  client_address: string;
  service_option: number;
  advance_percent: number;
  delivery_percent: number;
  completion_percent: number;
  margin_percent: number;
}

export interface QuotationResponse {
  id: string;
  project_id: string;
  reference_number: string;
  client_name: string;
  client_address: string;
  service_option: number;
  advance_percent: number;
  delivery_percent: number;
  completion_percent: number;
  margin_percent: number;
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
