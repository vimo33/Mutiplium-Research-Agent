import { useReducer, useEffect, useCallback, useMemo } from 'react';
import type { 
  ReviewState, 
  ReviewAction, 
  CompanyReview, 
  ReviewStatus, 
  DataQualityFlag 
} from '../types';
import type { CompanyData } from '../components/CompanyCard';

// LocalStorage key
const STORAGE_KEY = 'multiplium_reviews';

// Initial state
const initialState: ReviewState = {
  reviews: {},
  currentIndex: 0,
  filterStatus: 'all',
  sortBy: 'confidence',
};

// Reducer
function reviewReducer(state: ReviewState, action: ReviewAction): ReviewState {
  switch (action.type) {
    case 'SET_STATUS': {
      const existing = state.reviews[action.company] || createEmptyReview(action.company);
      return {
        ...state,
        reviews: {
          ...state.reviews,
          [action.company]: {
            ...existing,
            status: action.status,
            reviewedAt: new Date().toISOString(),
          },
        },
      };
    }
    
    case 'SET_SCORE': {
      const existing = state.reviews[action.company] || createEmptyReview(action.company);
      return {
        ...state,
        reviews: {
          ...state.reviews,
          [action.company]: {
            ...existing,
            score: action.score,
            reviewedAt: new Date().toISOString(),
          },
        },
      };
    }
    
    case 'SET_NOTES': {
      const existing = state.reviews[action.company] || createEmptyReview(action.company);
      return {
        ...state,
        reviews: {
          ...state.reviews,
          [action.company]: {
            ...existing,
            notes: action.notes,
            reviewedAt: new Date().toISOString(),
          },
        },
      };
    }
    
    case 'ADD_FLAG': {
      const existing = state.reviews[action.company] || createEmptyReview(action.company);
      const flags = existing.dataFlags.includes(action.flag) 
        ? existing.dataFlags 
        : [...existing.dataFlags, action.flag];
      return {
        ...state,
        reviews: {
          ...state.reviews,
          [action.company]: {
            ...existing,
            dataFlags: flags,
            status: flags.length > 0 ? 'needs_review' : existing.status,
          },
        },
      };
    }
    
    case 'REMOVE_FLAG': {
      const existing = state.reviews[action.company] || createEmptyReview(action.company);
      return {
        ...state,
        reviews: {
          ...state.reviews,
          [action.company]: {
            ...existing,
            dataFlags: existing.dataFlags.filter(f => f !== action.flag),
          },
        },
      };
    }
    
    case 'SET_DATA_EDIT': {
      const existing = state.reviews[action.company] || createEmptyReview(action.company);
      return {
        ...state,
        reviews: {
          ...state.reviews,
          [action.company]: {
            ...existing,
            dataEdits: {
              ...existing.dataEdits,
              [action.field]: action.value,
            },
            reviewedAt: new Date().toISOString(),
          },
        },
      };
    }
    
    case 'SET_FILTER':
      return { ...state, filterStatus: action.filter, currentIndex: 0 };
    
    case 'SET_SORT':
      return { ...state, sortBy: action.sortBy, currentIndex: 0 };
    
    case 'SET_INDEX':
      return { ...state, currentIndex: action.index };
    
    case 'NEXT':
      return { ...state, currentIndex: state.currentIndex + 1 };
    
    case 'PREV':
      return { ...state, currentIndex: Math.max(0, state.currentIndex - 1) };
    
    case 'LOAD_REVIEWS':
      return { ...state, reviews: action.reviews };
    
    case 'CLEAR_ALL':
      return { ...initialState };
    
    default:
      return state;
  }
}

// Helper to create empty review
function createEmptyReview(company: string): CompanyReview {
  return {
    company,
    status: 'pending',
    notes: '',
    dataFlags: [],
    reviewedAt: new Date().toISOString(),
  };
}

// Helper to detect data quality issues
export function detectDataQualityFlags(company: CompanyData): DataQualityFlag[] {
  const flags: DataQualityFlag[] = [];
  
  if (!company.website || company.website === 'N/A' || company.website === 'Unknown') {
    flags.push('missing_website');
  }
  
  const hasFinancials = company.financial_enrichment?.funding_rounds?.length || 
                        company.funding_rounds?.length;
  if (!hasFinancials) {
    flags.push('missing_financials');
  }
  
  if (!company.team?.founders?.length && !company.team?.size) {
    flags.push('missing_team');
  }
  
  const hasSwot = company.swot?.strengths?.length || 
                  company.swot?.weaknesses?.length ||
                  company.swot?.opportunities?.length ||
                  company.swot?.threats?.length;
  if (!hasSwot) {
    flags.push('missing_swot');
  }
  
  if ((company.confidence_0to1 ?? 0) < 0.6) {
    flags.push('low_confidence');
  }
  
  return flags;
}

// Main hook
export function useReviews(companies: CompanyData[] = []) {
  const [state, dispatch] = useReducer(reviewReducer, initialState);
  
  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        dispatch({ type: 'LOAD_REVIEWS', reviews: parsed });
      }
    } catch (e) {
      console.error('Failed to load reviews from localStorage:', e);
    }
  }, []);
  
  // Save to localStorage on changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.reviews));
    } catch (e) {
      console.error('Failed to save reviews to localStorage:', e);
    }
  }, [state.reviews]);
  
  // Initialize reviews for new companies (detect data quality issues)
  useEffect(() => {
    companies.forEach(company => {
      if (!state.reviews[company.company]) {
        const flags = detectDataQualityFlags(company);
        if (flags.length > 0) {
          flags.forEach(flag => {
            dispatch({ type: 'ADD_FLAG', company: company.company, flag });
          });
        }
      }
    });
  }, [companies, state.reviews]);
  
  // Filtered and sorted companies
  const filteredCompanies = useMemo(() => {
    let result = [...companies];
    
    // Apply filter
    if (state.filterStatus !== 'all') {
      if (state.filterStatus === 'flagged') {
        result = result.filter(c => {
          const review = state.reviews[c.company];
          return review?.dataFlags?.length > 0;
        });
      } else {
        result = result.filter(c => {
          const review = state.reviews[c.company];
          return review?.status === state.filterStatus || 
                 (!review && state.filterStatus === 'pending');
        });
      }
    }
    
    // Apply sort
    result.sort((a, b) => {
      const reviewA = state.reviews[a.company];
      const reviewB = state.reviews[b.company];
      
      switch (state.sortBy) {
        case 'confidence':
          return (b.confidence_0to1 ?? 0) - (a.confidence_0to1 ?? 0);
        case 'name':
          return a.company.localeCompare(b.company);
        case 'status': {
          const statusOrder: Record<ReviewStatus, number> = {
            pending: 0,
            needs_review: 1,
            maybe: 2,
            approved: 3,
            rejected: 4,
          };
          const statusA = reviewA?.status || 'pending';
          const statusB = reviewB?.status || 'pending';
          return statusOrder[statusA] - statusOrder[statusB];
        }
        case 'score':
          return (reviewB?.score ?? 0) - (reviewA?.score ?? 0);
        default:
          return 0;
      }
    });
    
    return result;
  }, [companies, state.reviews, state.filterStatus, state.sortBy]);
  
  // Current company
  const currentCompany = filteredCompanies[state.currentIndex] || null;
  const currentReview = currentCompany ? state.reviews[currentCompany.company] : null;
  
  // Statistics
  const stats = useMemo(() => {
    const total = companies.length;
    const reviewed = Object.values(state.reviews).filter(
      r => r.status !== 'pending'
    ).length;
    const approved = Object.values(state.reviews).filter(
      r => r.status === 'approved'
    ).length;
    const rejected = Object.values(state.reviews).filter(
      r => r.status === 'rejected'
    ).length;
    const maybe = Object.values(state.reviews).filter(
      r => r.status === 'maybe'
    ).length;
    const flagged = Object.values(state.reviews).filter(
      r => r.dataFlags?.length > 0
    ).length;
    const avgScore = Object.values(state.reviews)
      .filter(r => r.score)
      .reduce((sum, r, _, arr) => sum + (r.score || 0) / arr.length, 0);
    
    return {
      total,
      reviewed,
      pending: total - reviewed,
      approved,
      rejected,
      maybe,
      flagged,
      avgScore: avgScore || 0,
      percentComplete: total > 0 ? Math.round((reviewed / total) * 100) : 0,
    };
  }, [companies, state.reviews]);
  
  // Actions
  const setStatus = useCallback((company: string, status: ReviewStatus) => {
    dispatch({ type: 'SET_STATUS', company, status });
  }, []);
  
  const setScore = useCallback((company: string, score: number) => {
    dispatch({ type: 'SET_SCORE', company, score });
  }, []);
  
  const setNotes = useCallback((company: string, notes: string) => {
    dispatch({ type: 'SET_NOTES', company, notes });
  }, []);
  
  const addFlag = useCallback((company: string, flag: DataQualityFlag) => {
    dispatch({ type: 'ADD_FLAG', company, flag });
  }, []);
  
  const removeFlag = useCallback((company: string, flag: DataQualityFlag) => {
    dispatch({ type: 'REMOVE_FLAG', company, flag });
  }, []);
  
  const setDataEdit = useCallback((company: string, field: string, value: string) => {
    dispatch({ type: 'SET_DATA_EDIT', company, field, value });
  }, []);
  
  const setFilter = useCallback((filter: ReviewStatus | 'all' | 'flagged') => {
    dispatch({ type: 'SET_FILTER', filter });
  }, []);
  
  const setSort = useCallback((sortBy: 'confidence' | 'name' | 'status' | 'score') => {
    dispatch({ type: 'SET_SORT', sortBy });
  }, []);
  
  const goToIndex = useCallback((index: number) => {
    dispatch({ type: 'SET_INDEX', index });
  }, []);
  
  const goToNext = useCallback(() => {
    if (state.currentIndex < filteredCompanies.length - 1) {
      dispatch({ type: 'NEXT' });
    }
  }, [state.currentIndex, filteredCompanies.length]);
  
  const goToPrev = useCallback(() => {
    dispatch({ type: 'PREV' });
  }, []);
  
  const clearAll = useCallback(() => {
    dispatch({ type: 'CLEAR_ALL' });
  }, []);
  
  const getReview = useCallback((company: string): CompanyReview | undefined => {
    return state.reviews[company];
  }, [state.reviews]);
  
  // Quick actions (approve, reject, maybe + auto-advance)
  const approveAndNext = useCallback((company: string) => {
    setStatus(company, 'approved');
    goToNext();
  }, [setStatus, goToNext]);
  
  const rejectAndNext = useCallback((company: string) => {
    setStatus(company, 'rejected');
    goToNext();
  }, [setStatus, goToNext]);
  
  const maybeAndNext = useCallback((company: string) => {
    setStatus(company, 'maybe');
    goToNext();
  }, [setStatus, goToNext]);
  
  // Export reviewed companies
  const exportToCSV = useCallback(() => {
    const approvedCompanies = companies.filter(
      c => state.reviews[c.company]?.status === 'approved'
    );
    
    const headers = [
      'Company',
      'Website',
      'Country',
      'Segment',
      'Confidence',
      'Score',
      'Notes',
      'Team Size',
      'Total Funding',
    ];
    
    const rows = approvedCompanies.map(c => {
      const review = state.reviews[c.company];
      const funding = (c.financial_enrichment?.funding_rounds || c.funding_rounds || [])
        .reduce((sum, r) => sum + (r.amount || 0), 0);
      
      return [
        c.company,
        c.website || '',
        c.country || '',
        c.segment || '',
        String(c.confidence_0to1 || 0),
        String(review?.score || ''),
        `"${(review?.notes || '').replace(/"/g, '""')}"`,
        c.team?.size || '',
        String(funding),
      ];
    });
    
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `approved_companies_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [companies, state.reviews]);
  
  return {
    // State
    reviews: state.reviews,
    filterStatus: state.filterStatus,
    sortBy: state.sortBy,
    currentIndex: state.currentIndex,
    
    // Computed
    filteredCompanies,
    currentCompany,
    currentReview,
    stats,
    
    // Actions
    setStatus,
    setScore,
    setNotes,
    addFlag,
    removeFlag,
    setDataEdit,
    setFilter,
    setSort,
    goToIndex,
    goToNext,
    goToPrev,
    clearAll,
    getReview,
    
    // Quick actions
    approveAndNext,
    rejectAndNext,
    maybeAndNext,
    
    // Export
    exportToCSV,
  };
}

export type UseReviewsReturn = ReturnType<typeof useReviews>;

