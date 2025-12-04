import { CompanyData } from './CompanyCard';
import { Button, Badge, ConfidenceRing, SegmentTag, CountryTag, SwotDots } from './ui';
import './CompareView.css';

interface CompareViewProps {
  companies: CompanyData[];
  onClose: () => void;
  shortlistedCompanies: string[];
  onToggleShortlist: (company: string) => void;
}

const StarIcon = ({ filled }: { filled: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
    <path d="M8 1.5l1.76 3.57 3.94.57-2.85 2.78.67 3.93L8 10.47l-3.52 1.88.67-3.93L2.3 5.64l3.94-.57L8 1.5z" />
  </svg>
);

const LinkIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M5 9l4-4M6 3h5v5M3 5v6h6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function CompareView({ companies, onClose, shortlistedCompanies, onToggleShortlist }: CompareViewProps) {
  const formatFunding = (amount: number) => {
    if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
    if (amount >= 1000) return `$${(amount / 1000).toFixed(0)}K`;
    return `$${amount}`;
  };

  const getTotalFunding = (company: CompanyData) => {
    const rounds = company.financial_enrichment?.funding_rounds || company.funding_rounds || [];
    return rounds.reduce((sum, r) => sum + (r.amount || 0), 0);
  };

  const getFounderCount = (company: CompanyData) => {
    return company.team?.founders?.length || 0;
  };

  const getCaseStudyCount = (company: CompanyData) => {
    return company.evidence_of_impact?.case_studies?.length || 0;
  };

  const getAwardCount = (company: CompanyData) => {
    return company.evidence_of_impact?.awards?.length || 0;
  };

  return (
    <div className="compare-view">
      {/* Header */}
      <div className="compare-view__header">
        <div className="compare-view__title">
          <h1>Compare Companies</h1>
          <Badge variant="primary">{companies.length} companies</Badge>
        </div>
        <Button variant="ghost" onClick={onClose}>
          Back to Grid
        </Button>
      </div>

      {/* Comparison Table */}
      <div className="compare-table-wrapper">
        <table className="compare-table">
          <thead>
            <tr>
              <th className="compare-table__label-cell">Metric</th>
              {companies.map(company => (
                <th key={company.company} className="compare-table__company-cell">
                  <div className="compare-table__company-header">
                    <button
                      className={`compare-table__star ${shortlistedCompanies.includes(company.company) ? 'compare-table__star--active' : ''}`}
                      onClick={() => onToggleShortlist(company.company)}
                    >
                      <StarIcon filled={shortlistedCompanies.includes(company.company)} />
                    </button>
                    <span className="compare-table__company-name">{company.company}</span>
                    {company.website && (
                      <a href={company.website} target="_blank" rel="noopener noreferrer" className="compare-table__link">
                        <LinkIcon />
                      </a>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* Location */}
            <tr>
              <td className="compare-table__label-cell">Location</td>
              {companies.map(company => (
                <td key={company.company}>
                  {company.country ? <CountryTag country={company.country} /> : '—'}
                </td>
              ))}
            </tr>

            {/* Segment */}
            <tr>
              <td className="compare-table__label-cell">Segment</td>
              {companies.map(company => (
                <td key={company.company}>
                  {company.segment ? <SegmentTag segment={company.segment} /> : '—'}
                </td>
              ))}
            </tr>

            {/* Confidence */}
            <tr>
              <td className="compare-table__label-cell">Data Confidence</td>
              {companies.map(company => (
                <td key={company.company}>
                  <ConfidenceRing confidence={company.confidence_0to1 || 0.5} size="sm" />
                </td>
              ))}
            </tr>

            {/* Team Size */}
            <tr>
              <td className="compare-table__label-cell">Team Size</td>
              {companies.map(company => (
                <td key={company.company}>
                  <span className="compare-table__value">
                    {company.team?.size || 'Unknown'}
                  </span>
                </td>
              ))}
            </tr>

            {/* Founders */}
            <tr>
              <td className="compare-table__label-cell">Founders</td>
              {companies.map(company => (
                <td key={company.company}>
                  <span className="compare-table__value">
                    {getFounderCount(company) > 0 ? getFounderCount(company) : '—'}
                  </span>
                </td>
              ))}
            </tr>

            {/* Total Funding */}
            <tr>
              <td className="compare-table__label-cell">Total Funding</td>
              {companies.map(company => {
                const total = getTotalFunding(company);
                return (
                  <td key={company.company}>
                    <span className={`compare-table__value ${total > 0 ? 'compare-table__value--highlight' : ''}`}>
                      {total > 0 ? formatFunding(total) : 'Undisclosed'}
                    </span>
                  </td>
                );
              })}
            </tr>

            {/* Case Studies */}
            <tr>
              <td className="compare-table__label-cell">Case Studies</td>
              {companies.map(company => (
                <td key={company.company}>
                  <span className="compare-table__value">
                    {getCaseStudyCount(company) > 0 ? getCaseStudyCount(company) : '—'}
                  </span>
                </td>
              ))}
            </tr>

            {/* Awards */}
            <tr>
              <td className="compare-table__label-cell">Awards</td>
              {companies.map(company => (
                <td key={company.company}>
                  <span className="compare-table__value">
                    {getAwardCount(company) > 0 ? `🏆 ${getAwardCount(company)}` : '—'}
                  </span>
                </td>
              ))}
            </tr>

            {/* SWOT - Strengths */}
            <tr>
              <td className="compare-table__label-cell">Strengths</td>
              {companies.map(company => (
                <td key={company.company}>
                  <SwotDots count={company.swot?.strengths?.length || 0} variant="strength" />
                </td>
              ))}
            </tr>

            {/* SWOT - Weaknesses */}
            <tr>
              <td className="compare-table__label-cell">Weaknesses</td>
              {companies.map(company => (
                <td key={company.company}>
                  <SwotDots count={company.swot?.weaknesses?.length || 0} variant="weakness" />
                </td>
              ))}
            </tr>

            {/* SWOT - Opportunities */}
            <tr>
              <td className="compare-table__label-cell">Opportunities</td>
              {companies.map(company => (
                <td key={company.company}>
                  <SwotDots count={company.swot?.opportunities?.length || 0} variant="opportunity" />
                </td>
              ))}
            </tr>

            {/* SWOT - Threats */}
            <tr>
              <td className="compare-table__label-cell">Threats</td>
              {companies.map(company => (
                <td key={company.company}>
                  <SwotDots count={company.swot?.threats?.length || 0} variant="threat" />
                </td>
              ))}
            </tr>

            {/* Competitors */}
            <tr>
              <td className="compare-table__label-cell">Direct Competitors</td>
              {companies.map(company => {
                const competitors = (company as any).competitors?.direct || [];
                return (
                  <td key={company.company}>
                    <span className="compare-table__value">
                      {competitors.length > 0 ? competitors.length : '—'}
                    </span>
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Detailed Sections */}
      <div className="compare-view__details">
        {/* Summaries */}
        <section className="compare-view__section">
          <h2>Company Summaries</h2>
          <div className="compare-view__summaries">
            {companies.map(company => (
              <div key={company.company} className="compare-view__summary-card">
                <h3>{company.company}</h3>
                <p>{company.summary || 'No summary available'}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Key Strengths */}
        <section className="compare-view__section">
          <h2>Key Strengths</h2>
          <div className="compare-view__grid">
            {companies.map(company => (
              <div key={company.company} className="compare-view__list-card">
                <h3>{company.company}</h3>
                {company.swot?.strengths && company.swot.strengths.length > 0 ? (
                  <ul>
                    {company.swot.strengths.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="compare-view__empty">No strengths documented</p>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Key Risks */}
        <section className="compare-view__section">
          <h2>Key Risks (Weaknesses & Threats)</h2>
          <div className="compare-view__grid">
            {companies.map(company => (
              <div key={company.company} className="compare-view__list-card compare-view__list-card--risk">
                <h3>{company.company}</h3>
                <div className="compare-view__risk-lists">
                  {company.swot?.weaknesses && company.swot.weaknesses.length > 0 && (
                    <div>
                      <h4>Weaknesses</h4>
                      <ul>
                        {company.swot.weaknesses.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {company.swot?.threats && company.swot.threats.length > 0 && (
                    <div>
                      <h4>Threats</h4>
                      <ul>
                        {company.swot.threats.map((t, i) => (
                          <li key={i}>{t}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(!company.swot?.weaknesses?.length && !company.swot?.threats?.length) && (
                    <p className="compare-view__empty">No risks documented</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

