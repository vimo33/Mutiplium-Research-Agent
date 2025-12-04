import { useState } from 'react';
import { Button } from '../ui';
import './WizardSteps.css';

interface BriefStepProps {
  clientName: string;
  projectName: string;
  objective: string;
  onClientNameChange: (value: string) => void;
  onProjectNameChange: (value: string) => void;
  onObjectiveChange: (value: string) => void;
  onNext: () => void;
}

// Example prompts for inspiration
const exampleObjectives = [
  "Find early-stage AgTech companies solving water management challenges in the Mediterranean region",
  "Identify B2B SaaS companies in logistics/supply chain with $1-5M ARR and strong unit economics",
  "Research sustainable packaging startups in Europe with innovative materials or processes",
  "Discover fintech companies serving SMBs in emerging markets with mobile-first solutions",
];

export function BriefStep({
  clientName,
  projectName,
  objective,
  onClientNameChange,
  onProjectNameChange,
  onObjectiveChange,
  onNext,
}: BriefStepProps) {
  const [showExamples, setShowExamples] = useState(false);

  const isValid = clientName.trim() && projectName.trim() && objective.trim().length >= 20;

  return (
    <div className="wizard-step">
      <div className="wizard-step__header">
        <span className="wizard-step__number">1</span>
        <div>
          <h2 className="wizard-step__title">Research Brief</h2>
          <p className="wizard-step__subtitle">
            Tell us about your research objective. The more detail you provide, 
            the better we can tailor the investment thesis and company search.
          </p>
        </div>
      </div>

      <div className="wizard-step__form">
        {/* Client Name */}
        <div className="wizard-field">
          <label className="wizard-field__label">
            Who is this research for?
            <span className="wizard-field__required">*</span>
          </label>
          <input
            type="text"
            className="wizard-field__input"
            placeholder="e.g., Acme Ventures, Beta Capital"
            value={clientName}
            onChange={(e) => onClientNameChange(e.target.value)}
          />
          <span className="wizard-field__hint">
            The organization or fund this research is being conducted for
          </span>
        </div>

        {/* Project Name */}
        <div className="wizard-field">
          <label className="wizard-field__label">
            Project name
            <span className="wizard-field__required">*</span>
          </label>
          <input
            type="text"
            className="wizard-field__input"
            placeholder="e.g., Wine Tech Europe Q4 2024"
            value={projectName}
            onChange={(e) => onProjectNameChange(e.target.value)}
          />
          <span className="wizard-field__hint">
            A descriptive name to identify this research project
          </span>
        </div>

        {/* Research Objective */}
        <div className="wizard-field">
          <label className="wizard-field__label">
            Describe your research objective
            <span className="wizard-field__required">*</span>
          </label>
          <textarea
            className="wizard-field__textarea"
            placeholder="Describe what you're looking for: target sectors, company types, geographic focus, stage preferences, key characteristics..."
            value={objective}
            onChange={(e) => onObjectiveChange(e.target.value)}
            rows={5}
          />
          <div className="wizard-field__footer">
            <span className="wizard-field__hint">
              {objective.length < 20 
                ? `At least 20 characters required (${20 - objective.length} more)`
                : `${objective.length} characters`
              }
            </span>
            <button 
              type="button"
              className="wizard-field__example-btn"
              onClick={() => setShowExamples(!showExamples)}
            >
              {showExamples ? 'Hide examples' : 'See examples'}
            </button>
          </div>
        </div>

        {/* Example Objectives */}
        {showExamples && (
          <div className="wizard-examples">
            <h4 className="wizard-examples__title">Example research objectives:</h4>
            <div className="wizard-examples__list">
              {exampleObjectives.map((example, i) => (
                <button
                  key={i}
                  type="button"
                  className="wizard-examples__item"
                  onClick={() => onObjectiveChange(example)}
                >
                  <span className="wizard-examples__icon">💡</span>
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="wizard-step__nav">
        <div /> {/* Spacer */}
        <Button 
          variant="primary" 
          onClick={onNext}
          disabled={!isValid}
        >
          Continue
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Button>
      </div>
    </div>
  );
}

