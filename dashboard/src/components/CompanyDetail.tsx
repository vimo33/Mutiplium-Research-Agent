import { CompanyData } from './CompanyCard';
import { Card, Tag, Badge, SegmentTag, CountryTag, ConfidenceRing } from './ui';
import './CompanyDetail.css';

interface CompanyDetailProps {
  company: CompanyData;
  isShortlisted: boolean;
  onToggleShortlist: () => void;
  onClose: () => void;
}

// Icons
const StarIcon = ({ filled }: { filled: boolean }) => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
    <path d="M10 2.5l2.2 4.46 4.93.72-3.57 3.48.84 4.92L10 13.71l-4.4 2.37.84-4.92-3.57-3.48 4.93-.72L10 2.5z" />
  </svg>
);

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M15 5L5 15M5 5L15 15" strokeLinecap="round" />
  </svg>
);

const LinkIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M6 10l4-4M7 4h5v5M4 6v6h6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const UserIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="5" r="3" />
    <path d="M2 14c0-3.314 2.686-4 6-4s6 .686 6 4" strokeLinecap="round" />
  </svg>
);

export function CompanyDetail({ company, isShortlisted, onToggleShortlist, onClose }: CompanyDetailProps) {
  const swot = company.swot || {};
  const team = company.team || {};
  const evidence = company.evidence_of_impact || {};
  const fundingRounds = company.financial_enrichment?.funding_rounds || company.funding_rounds || [];
  const competitors = company.competitors;
  const keyClients = company.key_clients || [];
  
  const formatFunding = (amount: number, currency = 'USD') => {
    if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
    if (amount >= 1000) return `$${(amount / 1000).toFixed(0)}K`;
    return `$${amount}`;
  };

  return (
    <div className="company-detail">
      {/* Header */}
      <div className="company-detail__header">
        <div className="company-detail__header-content">
          <div className="company-detail__title-row">
            <h2 className="company-detail__name">{company.company}</h2>
            <div className="company-detail__actions">
              <button
                className={`company-detail__star ${isShortlisted ? 'company-detail__star--active' : ''}`}
                onClick={onToggleShortlist}
                aria-label={isShortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
              >
                <StarIcon filled={isShortlisted} />
              </button>
              <button className="company-detail__close" onClick={onClose}>
                <CloseIcon />
              </button>
            </div>
          </div>
          
          <div className="company-detail__meta">
            {company.segment && <SegmentTag segment={company.segment} />}
            {company.country && <CountryTag country={company.country} />}
            {company.website && (
              <a 
                href={company.website} 
                target="_blank" 
                rel="noopener noreferrer"
                className="company-detail__website"
              >
                <LinkIcon />
                Website
              </a>
            )}
          </div>
          
          <div className="company-detail__confidence">
            <ConfidenceRing confidence={company.confidence_0to1 || 0.5} size="md" />
            <span>Data Confidence</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="company-detail__content">
        {/* Overview */}
        <section className="company-detail__section">
          <h3 className="company-detail__section-title">Overview</h3>
          <p className="company-detail__overview">{company.summary}</p>
          
          {company.kpi_alignment && company.kpi_alignment.length > 0 && (
            <div className="company-detail__kpis">
              <h4 className="company-detail__subsection-title">KPI Alignment</h4>
              <ul className="company-detail__kpi-list">
                {company.kpi_alignment.map((kpi, i) => (
                  <li key={i}>{kpi}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Team */}
        {team && ((team.founders?.length ?? 0) > 0 || (team.executives?.length ?? 0) > 0 || team.size) && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">
              <UserIcon /> Team
            </h3>
            
            {team.size && (
              <div className="company-detail__team-size">
                <Badge variant="primary">{team.size}</Badge>
              </div>
            )}
            
            {team.founders && team.founders.length > 0 && (
              <div className="company-detail__team-group">
                <h4 className="company-detail__subsection-title">Founders</h4>
                <div className="company-detail__people">
                  {team.founders.map((founder: any, i: number) => {
                    // Handle both string and object formats
                    const founderName = typeof founder === 'string' ? founder : founder?.name || 'Unknown';
                    const founderBg = typeof founder === 'object' ? founder?.background : undefined;
                    if (founderName.toLowerCase().includes('not available') || founderName.toLowerCase().includes('not publicly')) {
                      return null;
                    }
                    return (
                      <div key={i} className="company-detail__person">
                        <div className="company-detail__person-avatar">
                          {founderName.charAt(0).toUpperCase()}
                        </div>
                        <div className="company-detail__person-info">
                          <span className="company-detail__person-name">{founderName}</span>
                          {founderBg && (
                            <span className="company-detail__person-role">{founderBg}</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            
            {team.executives && team.executives.length > 0 && (
              <div className="company-detail__team-group">
                <h4 className="company-detail__subsection-title">Leadership</h4>
                <div className="company-detail__people">
                  {team.executives.map((exec: any, i: number) => {
                    // Handle both string and object formats
                    let execName: string;
                    let execTitle: string | undefined;
                    
                    if (typeof exec === 'string') {
                      // Parse strings like "CEO: Jennifer Honeycutt"
                      const parts = exec.split(':');
                      if (parts.length === 2) {
                        execTitle = parts[0].trim();
                        execName = parts[1].trim();
                      } else {
                        execName = exec;
                      }
                    } else {
                      execName = exec?.name || 'Unknown';
                      execTitle = exec?.title;
                    }
                    
                    if (execName.toLowerCase().includes('not available') || execName.toLowerCase().includes('not publicly') || execName.toLowerCase().includes('not listed')) {
                      return null;
                    }
                    
                    return (
                      <div key={i} className="company-detail__person">
                        <div className="company-detail__person-avatar">
                          {execName.charAt(0).toUpperCase()}
                        </div>
                        <div className="company-detail__person-info">
                          <span className="company-detail__person-name">{execName}</span>
                          {execTitle && <span className="company-detail__person-role">{execTitle}</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Funding */}
        {fundingRounds.length > 0 && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">Funding History</h3>
            <div className="company-detail__funding-list">
              {fundingRounds.map((round, i) => (
                <div key={i} className="company-detail__funding-round">
                  <div className="company-detail__funding-header">
                    <Badge variant="primary">{round.round_type}</Badge>
                    {round.amount && (
                      <span className="company-detail__funding-amount">
                        {formatFunding(round.amount, round.currency)}
                      </span>
                    )}
                  </div>
                  {round.investors && round.investors.length > 0 && (
                    <div className="company-detail__funding-investors">
                      {round.investors.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* SWOT Analysis */}
        {(swot.strengths?.length || swot.weaknesses?.length || swot.opportunities?.length || swot.threats?.length) && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">SWOT Analysis</h3>
            <div className="company-detail__swot-grid">
              {swot.strengths && swot.strengths.length > 0 && (
                <div className="company-detail__swot-cell company-detail__swot-cell--strength">
                  <h4>Strengths</h4>
                  <ul>
                    {swot.strengths.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {swot.weaknesses && swot.weaknesses.length > 0 && (
                <div className="company-detail__swot-cell company-detail__swot-cell--weakness">
                  <h4>Weaknesses</h4>
                  <ul>
                    {swot.weaknesses.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {swot.opportunities && swot.opportunities.length > 0 && (
                <div className="company-detail__swot-cell company-detail__swot-cell--opportunity">
                  <h4>Opportunities</h4>
                  <ul>
                    {swot.opportunities.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {swot.threats && swot.threats.length > 0 && (
                <div className="company-detail__swot-cell company-detail__swot-cell--threat">
                  <h4>Threats</h4>
                  <ul>
                    {swot.threats.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Competitors */}
        {competitors && ((competitors.direct?.length ?? 0) > 0 || competitors.differentiation) && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">Competitive Landscape</h3>
            
            {competitors.differentiation && (
              <p className="company-detail__differentiation">{competitors.differentiation}</p>
            )}
            
            {competitors.direct && competitors.direct.length > 0 && (
              <div className="company-detail__competitors">
                <h4 className="company-detail__subsection-title">Direct Competitors</h4>
                <div className="company-detail__competitor-list">
                  {competitors.direct.map((comp: any, i: number) => (
                    <Card key={i} padding="sm" className="company-detail__competitor">
                      <span className="company-detail__competitor-name">{comp.name}</span>
                      {comp.description && (
                        <span className="company-detail__competitor-desc">{comp.description}</span>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Evidence of Impact */}
        {(evidence.case_studies?.length || evidence.awards?.length || evidence.academic_papers?.length) && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">Evidence of Impact</h3>
            
            {evidence.case_studies && evidence.case_studies.length > 0 && (
              <div className="company-detail__evidence-group">
                <h4 className="company-detail__subsection-title">Case Studies</h4>
                <ul className="company-detail__evidence-list">
                  {evidence.case_studies.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {evidence.awards && evidence.awards.length > 0 && (
              <div className="company-detail__evidence-group">
                <h4 className="company-detail__subsection-title">Awards & Recognition</h4>
                <div className="company-detail__awards">
                  {evidence.awards.map((award, i) => (
                    <Badge key={i} variant="warning">🏆 {award}</Badge>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Key Clients */}
        {keyClients.length > 0 && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">Key Clients</h3>
            <div className="company-detail__clients">
              {keyClients.map((client: any, i: number) => {
                // Handle both string and object formats
                const clientName = typeof client === 'string' ? client : client?.name || 'Unknown';
                const clientMarket = typeof client === 'object' ? client?.geographic_market : undefined;
                const clientRef = typeof client === 'object' ? client?.notable_reference : undefined;
                
                // Skip "not available" entries
                if (clientName.toLowerCase().includes('not available') || clientName.toLowerCase().includes('not publicly')) {
                  return null;
                }
                
                return (
                  <Card key={i} padding="sm" className="company-detail__client">
                    <span className="company-detail__client-name">{clientName}</span>
                    {clientMarket && (
                      <span className="company-detail__client-market">{clientMarket}</span>
                    )}
                    {clientRef && (
                      <span className="company-detail__client-ref">{clientRef}</span>
                    )}
                  </Card>
                );
              })}
            </div>
          </section>
        )}

        {/* Sources */}
        {company.sources && company.sources.length > 0 && (
          <section className="company-detail__section">
            <h3 className="company-detail__section-title">Sources</h3>
            <ul className="company-detail__sources">
              {company.sources.map((source: string, i: number) => {
                // Safely parse URL
                let hostname = source;
                try {
                  hostname = new URL(source).hostname;
                } catch {
                  // If not a valid URL, use the source as-is or truncate
                  hostname = source.length > 50 ? source.substring(0, 50) + '...' : source;
                }
                
                return (
                  <li key={i}>
                    <a href={source} target="_blank" rel="noopener noreferrer">
                      <LinkIcon />
                      {hostname}
                    </a>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

