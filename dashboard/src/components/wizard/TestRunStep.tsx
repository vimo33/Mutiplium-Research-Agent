import type { TestRunCompany, ValueChainSegment } from '../../types';
import { Button, Badge } from '../ui';
import './WizardSteps.css';

interface TestRunStepProps {
  valueChain: ValueChainSegment[];
  testCompanies: TestRunCompany[];
  isLoading: boolean;
  onBack: () => void;
  onApprove: () => void;
  onReject: () => void;
}

// Icons
const CheckCircleIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="10" cy="10" r="8" />
    <path d="M6 10l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 10a6 6 0 0111.3-2.7M16 10a6 6 0 01-11.3 2.7" strokeLinecap="round" />
    <path d="M16 4v4h-4M4 16v-4h4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function TestRunStep({
  valueChain,
  testCompanies,
  isLoading,
  onBack,
  onApprove,
  onReject,
}: TestRunStepProps) {
  // Group companies by segment
  const companiesBySegment: Record<string, TestRunCompany[]> = {};
  
  valueChain.forEach(vc => {
    companiesBySegment[vc.segment] = testCompanies.filter(
      c => c.segment === vc.segment
    );
  });

  // Count totals
  const totalFound = testCompanies.length;
  const expectedTotal = valueChain.length * 3;

  if (isLoading) {
    return (
      <div className="wizard-step">
        <div className="wizard-step__header">
          <span className="wizard-step__number">4</span>
          <div>
            <h2 className="wizard-step__title">Test Run in Progress</h2>
            <p className="wizard-step__subtitle">
              Finding sample companies across your value chain segments...
            </p>
          </div>
        </div>

        <div className="wizard-loading" style={{ padding: '40px' }}>
          <div className="wizard-loading__spinner" />
          <p className="wizard-loading__text">
            Searching for {expectedTotal} companies (3 per segment)
          </p>
        </div>

        <div className="wizard-test-preview">
          {valueChain.map((vc) => (
            <div key={vc.segment} className="wizard-test-segment">
              <div className="wizard-test-segment__header">
                {vc.segment}
                <Badge variant="default" size="sm">Searching...</Badge>
              </div>
              <div className="wizard-test-segment__companies">
                {[1, 2, 3].map(i => (
                  <div key={i} className="wizard-test-company" style={{ opacity: 0.3 }}>
                    Finding company {i}...
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-step">
      <div className="wizard-step__header">
        <span className="wizard-step__number">4</span>
        <div>
          <h2 className="wizard-step__title">Test Run Preview</h2>
          <p className="wizard-step__subtitle">
            We found {totalFound} sample companies across your value chain segments. 
            Review the results to ensure they match your investment criteria.
          </p>
        </div>
      </div>

      {/* Summary */}
      <div style={{ 
        display: 'flex', 
        gap: '12px', 
        marginBottom: '24px',
        flexWrap: 'wrap'
      }}>
        <Badge variant="primary">
          {totalFound} companies found
        </Badge>
        <Badge variant="default">
          {valueChain.length} segments
        </Badge>
        <Badge variant={totalFound >= expectedTotal * 0.7 ? 'success' : 'warning'}>
          {Math.round((totalFound / expectedTotal) * 100)}% coverage
        </Badge>
      </div>

      {/* Company Grid by Segment */}
      <div className="wizard-test-preview">
        {valueChain.map((vc) => {
          const segmentCompanies = companiesBySegment[vc.segment] || [];
          return (
            <div key={vc.segment} className="wizard-test-segment">
              <div className="wizard-test-segment__header">
                {vc.segment}
                <Badge 
                  variant={segmentCompanies.length >= 3 ? 'success' : segmentCompanies.length > 0 ? 'warning' : 'danger'}
                  size="sm"
                >
                  {segmentCompanies.length}
                </Badge>
              </div>
              <div className="wizard-test-segment__companies">
                {segmentCompanies.length > 0 ? (
                  segmentCompanies.map((company, idx) => (
                    <div key={idx} className="wizard-test-company">
                      <span>{company.company}</span>
                      {company.country && (
                        <span style={{ 
                          fontSize: '11px', 
                          color: 'var(--color-text-muted)',
                          marginLeft: 'auto'
                        }}>
                          {company.country}
                        </span>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="wizard-test-company" style={{ 
                    opacity: 0.5, 
                    fontStyle: 'italic' 
                  }}>
                    No companies found
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Decision prompt */}
      <div style={{ 
        padding: '20px', 
        background: 'var(--color-surface)', 
        border: '1px solid var(--color-border-subtle)',
        borderRadius: 'var(--radius-md)',
        marginTop: '24px'
      }}>
        <h4 style={{ 
          margin: '0 0 12px 0', 
          fontSize: '15px',
          color: 'var(--color-text-primary)' 
        }}>
          How does this sample look?
        </h4>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '12px' 
        }}>
          <label style={{ 
            display: 'flex', 
            alignItems: 'flex-start', 
            gap: '10px',
            padding: '12px',
            background: 'var(--color-surface-subtle)',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer'
          }}>
            <CheckCircleIcon />
            <div>
              <strong style={{ color: 'var(--color-success)' }}>
                Sample looks relevant
              </strong>
              <p style={{ 
                margin: '4px 0 0 0', 
                fontSize: '13px',
                color: 'var(--color-text-muted)' 
              }}>
                Proceed with full research to discover all companies in this space
              </p>
            </div>
          </label>
          <label style={{ 
            display: 'flex', 
            alignItems: 'flex-start', 
            gap: '10px',
            padding: '12px',
            background: 'var(--color-surface-subtle)',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer'
          }}>
            <RefreshIcon />
            <div>
              <strong style={{ color: 'var(--color-warning)' }}>
                Needs adjustment
              </strong>
              <p style={{ 
                margin: '4px 0 0 0', 
                fontSize: '13px',
                color: 'var(--color-text-muted)' 
              }}>
                Go back to refine the framework and regenerate sample
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Navigation */}
      <div className="wizard-step__nav">
        <Button variant="ghost" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 4l-4 4 4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Adjust Framework
        </Button>
        <Button variant="success" onClick={onApprove}>
          Approve & Start Full Research
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Button>
      </div>
    </div>
  );
}

