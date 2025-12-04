import { useState } from 'react';
import type { Project, ResearchFramework, KPI, ValueChainSegment } from '../types';
import { Button, Badge } from './ui';
import './ContextPanel.css';

interface ContextPanelProps {
  project: Project;
  onUpdateFramework?: (framework: Partial<ResearchFramework>) => void;
  isEditable?: boolean;
  compact?: boolean;
}

// Icons
const ChevronDownIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ChevronUpIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 10l4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const EditIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M10 2l2 2-8 8H2v-2l8-8z" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ClientIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="5" r="3" />
    <path d="M2 14c0-3 2.5-5 6-5s6 2 6 5" strokeLinecap="round" />
  </svg>
);

const TargetIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="6" />
    <circle cx="8" cy="8" r="3" />
    <circle cx="8" cy="8" r="1" fill="currentColor" />
  </svg>
);

export function ContextPanel({ 
  project, 
  onUpdateFramework, 
  isEditable = false,
  compact = false 
}: ContextPanelProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(compact ? [] : ['thesis', 'kpis', 'valueChain'])
  );
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const startEditing = (section: string, value: string) => {
    setEditingSection(section);
    setEditValue(value);
  };

  const saveEdit = () => {
    if (!editingSection || !onUpdateFramework) return;
    
    if (editingSection === 'thesis') {
      onUpdateFramework({ thesis: editValue });
    }
    setEditingSection(null);
    setEditValue('');
  };

  const { framework, clientName, brief } = project;

  return (
    <div className={`context-panel ${compact ? 'context-panel--compact' : ''}`}>
      {/* Client & Project Info */}
      <div className="context-panel__header">
        <div className="context-panel__client">
          <ClientIcon />
          <span>{clientName}</span>
        </div>
        {brief.geography && brief.geography.length > 0 && (
          <div className="context-panel__meta">
            <TargetIcon />
            <span>{brief.geography.join(', ')}</span>
          </div>
        )}
      </div>

      {/* Investment Thesis */}
      <div className="context-panel__section">
        <button 
          className="context-panel__section-header"
          onClick={() => toggleSection('thesis')}
        >
          <span className="context-panel__section-title">Investment Thesis</span>
          {expandedSections.has('thesis') ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>
        
        {expandedSections.has('thesis') && (
          <div className="context-panel__section-content">
            {editingSection === 'thesis' ? (
              <div className="context-panel__edit">
                <textarea
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  rows={5}
                  className="context-panel__textarea"
                />
                <div className="context-panel__edit-actions">
                  <Button size="sm" variant="ghost" onClick={() => setEditingSection(null)}>
                    Cancel
                  </Button>
                  <Button size="sm" variant="primary" onClick={saveEdit}>
                    Save
                  </Button>
                </div>
              </div>
            ) : (
              <div className="context-panel__thesis">
                <p>{framework.thesis}</p>
                {isEditable && onUpdateFramework && (
                  <button 
                    className="context-panel__edit-btn"
                    onClick={() => startEditing('thesis', framework.thesis)}
                  >
                    <EditIcon />
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* KPIs */}
      <div className="context-panel__section">
        <button 
          className="context-panel__section-header"
          onClick={() => toggleSection('kpis')}
        >
          <span className="context-panel__section-title">
            Key Performance Indicators
            <Badge variant="default" size="sm">{framework.kpis.length}</Badge>
          </span>
          {expandedSections.has('kpis') ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>
        
        {expandedSections.has('kpis') && (
          <div className="context-panel__section-content">
            <div className="context-panel__kpi-list">
              {framework.kpis.map((kpi, index) => (
                <div key={index} className="context-panel__kpi">
                  <div className="context-panel__kpi-header">
                    <span className="context-panel__kpi-name">{kpi.name}</span>
                    {kpi.target && (
                      <Badge variant="primary" size="sm">{kpi.target}</Badge>
                    )}
                  </div>
                  {kpi.rationale && (
                    <p className="context-panel__kpi-rationale">{kpi.rationale}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Value Chain */}
      <div className="context-panel__section">
        <button 
          className="context-panel__section-header"
          onClick={() => toggleSection('valueChain')}
        >
          <span className="context-panel__section-title">
            Value Chain
            <Badge variant="default" size="sm">{framework.valueChain.length}</Badge>
          </span>
          {expandedSections.has('valueChain') ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>
        
        {expandedSections.has('valueChain') && (
          <div className="context-panel__section-content">
            <div className="context-panel__value-chain">
              {framework.valueChain.map((vc, index) => (
                <div key={index} className="context-panel__segment">
                  <span className="context-panel__segment-name">{vc.segment}</span>
                  {vc.companyCount !== undefined && (
                    <Badge variant="default" size="sm">{vc.companyCount}</Badge>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Brief Summary (collapsed by default) */}
      <div className="context-panel__section">
        <button 
          className="context-panel__section-header"
          onClick={() => toggleSection('brief')}
        >
          <span className="context-panel__section-title">Research Brief</span>
          {expandedSections.has('brief') ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>
        
        {expandedSections.has('brief') && (
          <div className="context-panel__section-content">
            <p className="context-panel__brief">{brief.objective}</p>
            
            {brief.targetStages && brief.targetStages.length > 0 && (
              <div className="context-panel__brief-row">
                <span className="context-panel__brief-label">Stages:</span>
                <span>{brief.targetStages.join(', ')}</span>
              </div>
            )}
            
            {brief.investmentSize && (
              <div className="context-panel__brief-row">
                <span className="context-panel__brief-label">Investment:</span>
                <span>{brief.investmentSize}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

