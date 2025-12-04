import { useState, useCallback } from 'react';
import type { CompanyData } from './CompanyCard';
import type { CompanyReview, DataQualityFlag } from '../types';
import { Button, Badge } from './ui';
import './DataQualityPanel.css';

interface DataQualityPanelProps {
  company: CompanyData;
  review?: CompanyReview;
  onAddFlag: (flag: DataQualityFlag) => void;
  onRemoveFlag: (flag: DataQualityFlag) => void;
  onEditField: (field: string, value: string) => void;
  onClose: () => void;
}

// Icons
const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const WarningIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 1L14 13H2L8 1z" />
    <path d="M8 6v3M8 11h.01" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 8l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SparkleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 0l1.5 4.5L14 6l-4.5 1.5L8 12l-1.5-4.5L2 6l4.5-1.5L8 0z" />
  </svg>
);

const EditIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M10 1l3 3-8 8H2v-3l8-8z" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// Field configurations
const EDITABLE_FIELDS: Array<{
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'url';
  flag?: DataQualityFlag;
  getValue: (c: CompanyData) => string;
}> = [
  {
    key: 'website',
    label: 'Website',
    type: 'url',
    flag: 'missing_website',
    getValue: (c) => c.website || '',
  },
  {
    key: 'country',
    label: 'Country',
    type: 'text',
    getValue: (c) => c.country || '',
  },
  {
    key: 'team_size',
    label: 'Team Size',
    type: 'text',
    flag: 'missing_team',
    getValue: (c) => c.team?.size || '',
  },
  {
    key: 'summary',
    label: 'Summary',
    type: 'textarea',
    getValue: (c) => c.summary || '',
  },
];

// Flag labels
const flagLabels: Record<DataQualityFlag, string> = {
  missing_website: 'Missing website',
  missing_financials: 'Missing financials',
  missing_team: 'Missing team data',
  missing_swot: 'Missing SWOT analysis',
  low_confidence: 'Low confidence score',
  incorrect_data: 'Data flagged as incorrect',
};

export function DataQualityPanel({
  company,
  review,
  onAddFlag,
  onRemoveFlag,
  onEditField,
  onClose,
}: DataQualityPanelProps) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [isEnriching, setIsEnriching] = useState(false);
  const [enrichError, setEnrichError] = useState<string | null>(null);
  
  const flags = review?.dataFlags || [];
  const edits = review?.dataEdits || {};
  
  // Start editing a field
  const startEdit = useCallback((field: string, currentValue: string) => {
    setEditingField(field);
    setEditValue(edits[field] || currentValue);
  }, [edits]);
  
  // Save edit
  const saveEdit = useCallback(() => {
    if (editingField && editValue.trim()) {
      onEditField(editingField, editValue.trim());
      // Remove related flag if present
      const fieldConfig = EDITABLE_FIELDS.find(f => f.key === editingField);
      if (fieldConfig?.flag && flags.includes(fieldConfig.flag)) {
        onRemoveFlag(fieldConfig.flag);
      }
    }
    setEditingField(null);
    setEditValue('');
  }, [editingField, editValue, onEditField, onRemoveFlag, flags]);
  
  // Cancel edit
  const cancelEdit = useCallback(() => {
    setEditingField(null);
    setEditValue('');
  }, []);
  
  // Toggle flag
  const toggleFlag = useCallback((flag: DataQualityFlag) => {
    if (flags.includes(flag)) {
      onRemoveFlag(flag);
    } else {
      onAddFlag(flag);
    }
  }, [flags, onAddFlag, onRemoveFlag]);
  
  // Enrich with GPT-4o
  const enrichWithAI = useCallback(async () => {
    setIsEnriching(true);
    setEnrichError(null);
    
    try {
      // Call the backend API to enrich company data
      const response = await fetch('http://localhost:8000/enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: company.company,
          existing_data: {
            summary: company.summary,
            website: company.website,
            country: company.country,
          },
          fields_to_enrich: flags.map(f => {
            switch (f) {
              case 'missing_website': return 'website';
              case 'missing_team': return 'team';
              case 'missing_financials': return 'financials';
              case 'missing_swot': return 'swot';
              default: return null;
            }
          }).filter(Boolean),
        }),
      });
      
      if (!response.ok) {
        throw new Error('Enrichment request failed');
      }
      
      const data = await response.json();
      
      // Apply enriched data as edits
      if (data.website) {
        onEditField('website', data.website);
        onRemoveFlag('missing_website');
      }
      if (data.team_size) {
        onEditField('team_size', data.team_size);
        onRemoveFlag('missing_team');
      }
      if (data.summary) {
        onEditField('summary', data.summary);
      }
      
    } catch (err) {
      setEnrichError('Failed to enrich data. Make sure the API server is running.');
    } finally {
      setIsEnriching(false);
    }
  }, [company, flags, onEditField, onRemoveFlag]);
  
  // Get display value (edit override or original)
  const getDisplayValue = (field: string, originalValue: string) => {
    return edits[field] || originalValue;
  };
  
  // Check if field has been edited
  const isEdited = (field: string) => !!edits[field];
  
  return (
    <div className="data-quality-panel">
      {/* Header */}
      <div className="data-quality-panel__header">
        <h2 className="data-quality-panel__title">Data Quality</h2>
        <button 
          className="data-quality-panel__close"
          onClick={onClose}
          aria-label="Close panel"
        >
          <CloseIcon />
        </button>
      </div>
      
      {/* Company name */}
      <div className="data-quality-panel__company">
        <h3>{company.company}</h3>
        {company.confidence_0to1 && (
          <Badge variant={company.confidence_0to1 >= 0.7 ? 'success' : 'warning'}>
            {Math.round(company.confidence_0to1 * 100)}% confidence
          </Badge>
        )}
      </div>
      
      {/* AI Enrichment */}
      {flags.length > 0 && (
        <div className="data-quality-panel__enrich">
          <Button
            variant="primary"
            onClick={enrichWithAI}
            disabled={isEnriching}
            loading={isEnriching}
          >
            <SparkleIcon />
            {isEnriching ? 'Enriching...' : 'Enrich with AI'}
          </Button>
          <p className="data-quality-panel__enrich-help">
            Uses GPT-4o to fill missing data fields
          </p>
          {enrichError && (
            <p className="data-quality-panel__error">{enrichError}</p>
          )}
        </div>
      )}
      
      {/* Flags section */}
      <div className="data-quality-panel__section">
        <h4 className="data-quality-panel__section-title">Data Flags</h4>
        <div className="data-quality-panel__flags">
          {(Object.keys(flagLabels) as DataQualityFlag[]).map(flag => (
            <button
              key={flag}
              className={`data-quality-panel__flag ${flags.includes(flag) ? 'data-quality-panel__flag--active' : ''}`}
              onClick={() => toggleFlag(flag)}
            >
              {flags.includes(flag) ? <WarningIcon /> : <CheckIcon />}
              {flagLabels[flag]}
            </button>
          ))}
        </div>
      </div>
      
      {/* Editable fields */}
      <div className="data-quality-panel__section">
        <h4 className="data-quality-panel__section-title">Company Data</h4>
        <div className="data-quality-panel__fields">
          {EDITABLE_FIELDS.map(field => {
            const originalValue = field.getValue(company);
            const displayValue = getDisplayValue(field.key, originalValue);
            const isMissing = !displayValue || displayValue === 'Unknown' || displayValue === 'N/A';
            const edited = isEdited(field.key);
            const isEditing = editingField === field.key;
            
            return (
              <div 
                key={field.key} 
                className={`data-quality-panel__field ${isMissing ? 'data-quality-panel__field--missing' : ''} ${edited ? 'data-quality-panel__field--edited' : ''}`}
              >
                <div className="data-quality-panel__field-header">
                  <label className="data-quality-panel__field-label">
                    {field.label}
                    {edited && <span className="data-quality-panel__edited-badge">Edited</span>}
                  </label>
                  {!isEditing && (
                    <button
                      className="data-quality-panel__field-edit"
                      onClick={() => startEdit(field.key, displayValue)}
                      aria-label={`Edit ${field.label}`}
                    >
                      <EditIcon />
                    </button>
                  )}
                </div>
                
                {isEditing ? (
                  <div className="data-quality-panel__field-edit-mode">
                    {field.type === 'textarea' ? (
                      <textarea
                        className="data-quality-panel__input"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        rows={3}
                        autoFocus
                      />
                    ) : (
                      <input
                        type={field.type === 'url' ? 'url' : 'text'}
                        className="data-quality-panel__input"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        placeholder={`Enter ${field.label.toLowerCase()}`}
                        autoFocus
                      />
                    )}
                    <div className="data-quality-panel__field-actions">
                      <Button size="sm" variant="primary" onClick={saveEdit}>
                        Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={cancelEdit}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="data-quality-panel__field-value">
                    {isMissing ? (
                      <span className="data-quality-panel__missing">Not available</span>
                    ) : field.type === 'url' ? (
                      <a href={displayValue} target="_blank" rel="noopener noreferrer">
                        {displayValue}
                      </a>
                    ) : (
                      displayValue
                    )}
                    {edited && originalValue && originalValue !== displayValue && (
                      <span className="data-quality-panel__original">
                        Original: {originalValue || 'N/A'}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      
      {/* Notes section */}
      <div className="data-quality-panel__section">
        <h4 className="data-quality-panel__section-title">Review Notes</h4>
        <textarea
          className="data-quality-panel__notes"
          placeholder="Add notes about this company..."
          value={review?.notes || ''}
          onChange={(e) => onEditField('_notes', e.target.value)}
          rows={4}
        />
      </div>
    </div>
  );
}

