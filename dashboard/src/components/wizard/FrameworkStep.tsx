import { useState } from 'react';
import type { ResearchFramework, KPI, ValueChainSegment } from '../../types';
import { Button, Badge } from '../ui';
import './WizardSteps.css';

interface FrameworkStepProps {
  framework: ResearchFramework;
  isLoading: boolean;
  onThesisChange: (thesis: string) => void;
  onKPIsChange: (kpis: KPI[]) => void;
  onValueChainChange: (valueChain: ValueChainSegment[]) => void;
  onBack: () => void;
  onNext: () => void;
}

// Icons
const EditIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M10 2l2 2-8 8H2v-2l8-8z" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SaveIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M3 7l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M7 3v8M3 7h8" strokeLinecap="round" />
  </svg>
);

const TrashIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 4h10M5 4V3a1 1 0 011-1h2a1 1 0 011 1v1M11 4v8a1 1 0 01-1 1H4a1 1 0 01-1-1V4" strokeLinecap="round" />
  </svg>
);

export function FrameworkStep({
  framework,
  isLoading,
  onThesisChange,
  onKPIsChange,
  onValueChainChange,
  onBack,
  onNext,
}: FrameworkStepProps) {
  // Edit states
  const [editingThesis, setEditingThesis] = useState(false);
  const [editingKPIs, setEditingKPIs] = useState(false);
  const [editingValueChain, setEditingValueChain] = useState(false);
  
  // Local edit values
  const [localThesis, setLocalThesis] = useState(framework.thesis);
  const [localKPIs, setLocalKPIs] = useState<KPI[]>(framework.kpis);
  const [localValueChain, setLocalValueChain] = useState<ValueChainSegment[]>(framework.valueChain);
  
  // New item inputs
  const [newKPIName, setNewKPIName] = useState('');
  const [newKPITarget, setNewKPITarget] = useState('');
  const [newSegment, setNewSegment] = useState('');

  // Save handlers
  const saveThesis = () => {
    onThesisChange(localThesis);
    setEditingThesis(false);
  };

  const saveKPIs = () => {
    onKPIsChange(localKPIs);
    setEditingKPIs(false);
  };

  const saveValueChain = () => {
    onValueChainChange(localValueChain);
    setEditingValueChain(false);
  };

  // KPI handlers
  const addKPI = () => {
    if (newKPIName.trim()) {
      setLocalKPIs([...localKPIs, { 
        name: newKPIName.trim(), 
        target: newKPITarget.trim(),
        rationale: '' 
      }]);
      setNewKPIName('');
      setNewKPITarget('');
    }
  };

  const removeKPI = (index: number) => {
    setLocalKPIs(localKPIs.filter((_, i) => i !== index));
  };

  // Value chain handlers
  const addSegment = () => {
    if (newSegment.trim()) {
      setLocalValueChain([...localValueChain, { 
        segment: newSegment.trim(), 
        description: '' 
      }]);
      setNewSegment('');
    }
  };

  const removeSegment = (index: number) => {
    setLocalValueChain(localValueChain.filter((_, i) => i !== index));
  };

  // Validation
  const isValid = framework.thesis.trim() && 
                  framework.kpis.length > 0 && 
                  framework.valueChain.length > 0;

  if (isLoading) {
    return (
      <div className="wizard-step">
        <div className="wizard-loading">
          <div className="wizard-loading__spinner" />
          <p className="wizard-loading__text">
            Generating your investment framework...
          </p>
        </div>
        <div className="wizard-generating">
          <span>AI is creating your thesis, KPIs, and value chain</span>
          <div className="wizard-generating__dots">
            <span className="wizard-generating__dot" />
            <span className="wizard-generating__dot" />
            <span className="wizard-generating__dot" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-step">
      <div className="wizard-step__header">
        <span className="wizard-step__number">3</span>
        <div>
          <h2 className="wizard-step__title">Review Framework</h2>
          <p className="wizard-step__subtitle">
            We've generated an investment framework based on your brief. 
            Review and edit each section to refine the research scope.
          </p>
        </div>
      </div>

      <div className="wizard-step__form">
        {/* Investment Thesis */}
        <div className="wizard-card">
          <div className="wizard-card__header">
            <h4 className="wizard-card__title">Investment Thesis</h4>
            {editingThesis ? (
              <button className="wizard-card__edit-btn" onClick={saveThesis}>
                <SaveIcon />
                Save
              </button>
            ) : (
              <button className="wizard-card__edit-btn" onClick={() => setEditingThesis(true)}>
                <EditIcon />
                Edit
              </button>
            )}
          </div>
          {editingThesis ? (
            <div className="wizard-card__content wizard-card__content--editing">
              <textarea
                value={localThesis}
                onChange={(e) => setLocalThesis(e.target.value)}
                rows={5}
              />
            </div>
          ) : (
            <p className="wizard-card__content">{framework.thesis}</p>
          )}
        </div>

        {/* KPIs */}
        <div className="wizard-card">
          <div className="wizard-card__header">
            <h4 className="wizard-card__title">Key Performance Indicators</h4>
            {editingKPIs ? (
              <button className="wizard-card__edit-btn" onClick={saveKPIs}>
                <SaveIcon />
                Done
              </button>
            ) : (
              <button className="wizard-card__edit-btn" onClick={() => setEditingKPIs(true)}>
                <EditIcon />
                Edit
              </button>
            )}
          </div>
          <div className="wizard-kpi-list">
            {(editingKPIs ? localKPIs : framework.kpis).map((kpi, index) => (
              <div key={index} className="wizard-kpi-item">
                <span className="wizard-kpi-item__bullet" />
                <div className="wizard-kpi-item__content">
                  <span className="wizard-kpi-item__name">{kpi.name}</span>
                  {kpi.target && (
                    <span className="wizard-kpi-item__target">Target: {kpi.target}</span>
                  )}
                </div>
                {editingKPIs && (
                  <button 
                    className="wizard-card__edit-btn"
                    onClick={() => removeKPI(index)}
                    style={{ color: 'var(--color-danger)' }}
                  >
                    <TrashIcon />
                  </button>
                )}
              </div>
            ))}
            {editingKPIs && (
              <div className="wizard-kpi-item" style={{ background: 'transparent', padding: '8px 0' }}>
                <input
                  type="text"
                  className="wizard-field__input"
                  placeholder="KPI name..."
                  value={newKPIName}
                  onChange={(e) => setNewKPIName(e.target.value)}
                  style={{ flex: 1, padding: '8px 12px', fontSize: '13px' }}
                />
                <input
                  type="text"
                  className="wizard-field__input"
                  placeholder="Target..."
                  value={newKPITarget}
                  onChange={(e) => setNewKPITarget(e.target.value)}
                  style={{ width: '120px', padding: '8px 12px', fontSize: '13px' }}
                />
                <button 
                  className="wizard-card__edit-btn"
                  onClick={addKPI}
                  disabled={!newKPIName.trim()}
                >
                  <PlusIcon />
                  Add
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Value Chain */}
        <div className="wizard-card">
          <div className="wizard-card__header">
            <h4 className="wizard-card__title">Value Chain Segments</h4>
            {editingValueChain ? (
              <button className="wizard-card__edit-btn" onClick={saveValueChain}>
                <SaveIcon />
                Done
              </button>
            ) : (
              <button className="wizard-card__edit-btn" onClick={() => setEditingValueChain(true)}>
                <EditIcon />
                Edit
              </button>
            )}
          </div>
          <div className="wizard-value-chain">
            {(editingValueChain ? localValueChain : framework.valueChain).map((vc, index) => (
              <span key={index} className="wizard-value-chain__tag">
                {vc.segment}
                {editingValueChain && (
                  <button
                    onClick={() => removeSegment(index)}
                    style={{ 
                      marginLeft: '8px', 
                      background: 'none', 
                      border: 'none', 
                      cursor: 'pointer',
                      color: 'var(--color-danger)',
                      padding: 0,
                    }}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
            {editingValueChain && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  className="wizard-field__input"
                  placeholder="Add segment..."
                  value={newSegment}
                  onChange={(e) => setNewSegment(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addSegment()}
                  style={{ width: '150px', padding: '6px 12px', fontSize: '13px' }}
                />
                <button 
                  className="wizard-card__edit-btn"
                  onClick={addSegment}
                  disabled={!newSegment.trim()}
                >
                  <PlusIcon />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Info note */}
        <div style={{ 
          padding: '12px 16px', 
          background: 'var(--color-surface-subtle)', 
          borderRadius: 'var(--radius-md)',
          fontSize: '13px',
          color: 'var(--color-text-muted)'
        }}>
          💡 The test run will search for 3 companies per value chain segment to validate the research scope before running full discovery.
        </div>
      </div>

      {/* Navigation */}
      <div className="wizard-step__nav">
        <Button variant="ghost" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 4l-4 4 4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </Button>
        <Button 
          variant="primary" 
          onClick={onNext}
          disabled={!isValid}
        >
          Start Test Run
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Button>
      </div>
    </div>
  );
}

