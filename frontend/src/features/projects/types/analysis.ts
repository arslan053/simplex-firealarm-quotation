export interface AnalysisAnswerResponse {
  id: string;
  project_id: string;
  question_id: string;
  question_no: number;
  question_text: string;
  category: string;
  answer: string;
  confidence: string;
  supporting_notes: string[];
  inferred_from: string;
  created_at: string | null;
}

export interface AnalysisResultResponse {
  project_id: string;
  answers: AnalysisAnswerResponse[];
  status: string;
  message: string;
  final_protocol: string | null;
  protocol_auto: string | null;
}
