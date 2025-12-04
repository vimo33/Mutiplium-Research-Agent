export type ProviderSnapshot = {
  name: string;
  status: string;
  progress: number;
  last_message?: string | null;
  tool_calls?: number;
  companies_found?: number;
  errors?: string[];
};

export type RunSnapshot = {
  run_id: string;
  project_id: string;
  status: string;
  phase: string;
  percent_complete: number;
  started_at: string;
  finished_at?: string | null;
  config_path?: string | null;
  params?: Record<string, unknown>;
  report_path?: string | null;
  providers: Record<string, ProviderSnapshot>;
  last_event?: Record<string, unknown> | null;
};

export type RunEvent = {
  ts: string;
  type: string;
  [key: string]: unknown;
};

// ============================================================================
// Review System Types
// ============================================================================

export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'maybe' | 'needs_review';

export type DataQualityFlag = 
  | 'missing_website' 
  | 'missing_financials' 
  | 'missing_team' 
  | 'missing_swot'
  | 'low_confidence' 
  | 'incorrect_data';

export interface CompanyReview {
  company: string;
  status: ReviewStatus;
  score?: number;           // 1-5 investment score
  notes: string;
  dataFlags: DataQualityFlag[];
  reviewedAt: string;
  reviewedBy?: string;
  dataEdits?: Record<string, string>;  // Field overrides
}

export interface ReviewState {
  reviews: Record<string, CompanyReview>;
  currentIndex: number;
  filterStatus: ReviewStatus | 'all' | 'flagged';
  sortBy: 'confidence' | 'name' | 'status' | 'score';
}

export type ReviewAction =
  | { type: 'SET_STATUS'; company: string; status: ReviewStatus }
  | { type: 'SET_SCORE'; company: string; score: number }
  | { type: 'SET_NOTES'; company: string; notes: string }
  | { type: 'ADD_FLAG'; company: string; flag: DataQualityFlag }
  | { type: 'REMOVE_FLAG'; company: string; flag: DataQualityFlag }
  | { type: 'SET_DATA_EDIT'; company: string; field: string; value: string }
  | { type: 'SET_FILTER'; filter: ReviewStatus | 'all' | 'flagged' }
  | { type: 'SET_SORT'; sortBy: 'confidence' | 'name' | 'status' | 'score' }
  | { type: 'SET_INDEX'; index: number }
  | { type: 'NEXT' }
  | { type: 'PREV' }
  | { type: 'LOAD_REVIEWS'; reviews: Record<string, CompanyReview> }
  | { type: 'CLEAR_ALL' };

