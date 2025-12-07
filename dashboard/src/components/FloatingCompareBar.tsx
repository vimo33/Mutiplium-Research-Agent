import { CompanyData } from './CompanyCard';
import { Button, Badge } from './ui';
import './FloatingCompareBar.css';

interface FloatingCompareBarProps {
  selectedCompanies: CompanyData[];
  onRemove: (companyName: string) => void;
  onClear: () => void;
  onCompare: () => void;
  maxCompanies?: number;
}

const CloseIcon = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 2l8 8M10 2l-8 8" strokeLinecap="round" />
  </svg>
);

const CompareIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="2" width="5" height="14" rx="1" />
    <rect x="11" y="2" width="5" height="14" rx="1" />
    <path d="M8.5 5h1M8.5 9h1M8.5 13h1" strokeLinecap="round" />
  </svg>
);

export function FloatingCompareBar({
  selectedCompanies,
  onRemove,
  onClear,
  onCompare,
  maxCompanies = 4,
}: FloatingCompareBarProps) {
  if (selectedCompanies.length === 0) return null;

  const canCompare = selectedCompanies.length >= 2;

  return (
    <div className="floating-compare-bar">
      <div className="floating-compare-bar__content">
        <div className="floating-compare-bar__info">
          <CompareIcon />
          <span className="floating-compare-bar__label">Compare</span>
          <Badge variant="primary" size="sm">
            {selectedCompanies.length}/{maxCompanies}
          </Badge>
        </div>

        <div className="floating-compare-bar__chips">
          {selectedCompanies.map((company) => (
            <div key={company.company} className="floating-compare-bar__chip">
              <span className="floating-compare-bar__chip-name">
                {company.company.length > 20 
                  ? company.company.slice(0, 20) + '...' 
                  : company.company}
              </span>
              <button
                className="floating-compare-bar__chip-remove"
                onClick={() => onRemove(company.company)}
              >
                <CloseIcon />
              </button>
            </div>
          ))}
          
          {Array.from({ length: maxCompanies - selectedCompanies.length }).map((_, i) => (
            <div key={`empty-${i}`} className="floating-compare-bar__chip floating-compare-bar__chip--empty">
              <span>Select company</span>
            </div>
          ))}
        </div>

        <div className="floating-compare-bar__actions">
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
          <Button 
            variant="primary" 
            size="sm" 
            onClick={onCompare}
            disabled={!canCompare}
          >
            {canCompare ? 'Compare Now' : 'Select 2+'}
          </Button>
        </div>
      </div>
    </div>
  );
}

