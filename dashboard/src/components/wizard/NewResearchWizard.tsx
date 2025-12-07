import { useState, useCallback } from 'react';
import type { 
  Project, 
  ResearchBrief, 
  ResearchFramework, 
  KPI,
  ValueChainSegment,
} from '../../types';
import type { ChatArtifacts } from '../../hooks';
import { ChatWizard } from './ChatWizard';
import { FrameworkStep } from './FrameworkStep';
import './NewResearchWizard.css';

// API base URL
const API_BASE = 'http://localhost:8000';

type WizardStep = 'setup' | 'chat' | 'framework';

interface NewResearchWizardProps {
  onComplete: (project: Partial<Project>) => void;
  onCancel: () => void;
}

// Progress steps config for the simplified flow
const steps: { id: WizardStep; label: string }[] = [
  { id: 'setup', label: 'Project Info' },
  { id: 'chat', label: 'Context Guide' },
  { id: 'framework', label: 'Review & Launch' },
];

export function NewResearchWizard({ onComplete, onCancel }: NewResearchWizardProps) {
  // Current step
  const [currentStep, setCurrentStep] = useState<WizardStep>('setup');
  
  // Basic project info
  const [clientName, setClientName] = useState('');
  const [projectName, setProjectName] = useState('');
  
  // Project ID (for API calls)
  const [projectId, setProjectId] = useState<string | null>(null);
  
  // Brief summary from chat conversation
  const [briefSummary, setBriefSummary] = useState('');
  
  // Framework (populated from chat)
  const [framework, setFramework] = useState<ResearchFramework>({
    thesis: '',
    kpis: [],
    valueChain: [],
  });

  // Step navigation
  const goToStep = (step: WizardStep) => setCurrentStep(step);

  // Handle setup completion - move to chat
  const handleSetupComplete = async () => {
    // Create project in backend first
    try {
      const response = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_name: clientName,
          project_name: projectName,
          brief: {
            objective: '',
            target_stages: [],
            investment_size: '',
            geography: [],
            technologies: [],
            additional_notes: '',
          },
        }),
      });
      
      if (response.ok) {
        const data = await response.json();
        setProjectId(data.project?.id || null);
      }
    } catch (err) {
      console.error('Failed to create project:', err);
    }
    
    goToStep('chat');
  };

  // Handle chat completion - receive artifacts from conversation
  const handleChatComplete = useCallback((artifacts: ChatArtifacts, summary: string) => {
    setBriefSummary(summary);
    setFramework({
      thesis: artifacts.thesis || '',
      kpis: artifacts.kpis,
      valueChain: artifacts.valueChain,
    });
    goToStep('framework');
  }, []);

  // Handle framework changes
  const handleThesisChange = useCallback((thesis: string) => {
    setFramework(prev => ({ ...prev, thesis }));
  }, []);

  const handleKPIsChange = useCallback((kpis: KPI[]) => {
    setFramework(prev => ({ ...prev, kpis }));
  }, []);

  const handleValueChainChange = useCallback((valueChain: ValueChainSegment[]) => {
    setFramework(prev => ({ ...prev, valueChain }));
  }, []);

  // Handle framework completion - start discovery directly
  const handleStartDiscovery = async () => {
    // Start the discovery run via API
    if (projectId) {
      try {
        const response = await fetch(`${API_BASE}/projects/${projectId}/start-discovery`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            framework: {
              thesis: framework.thesis,
              kpis: framework.kpis.map(k => ({
                name: k.name,
                target: k.target,
                rationale: k.rationale,
              })),
              value_chain: framework.valueChain.map(v => ({
                segment: v.segment,
                description: v.description,
              })),
            },
            top_n: 50,
          }),
        });

        if (!response.ok) {
          console.error('Failed to start discovery');
        }
      } catch (err) {
        console.error('Error starting discovery:', err);
      }
    }

    const project: Partial<Project> = {
      id: projectId || undefined,
      clientName,
      projectName,
      brief: {
        objective: briefSummary || framework.thesis.slice(0, 500),
        targetStages: [],
        investmentSize: '',
        geography: [],
        technologies: [],
        additionalNotes: '',
      },
      framework,
      status: 'researching',
    };
    onComplete(project);
  };

  // Get current step index
  const currentStepIndex = steps.findIndex(s => s.id === currentStep);

  // Render setup step (basic project info before chat)
  const renderSetupStep = () => (
    <div className="wizard-step">
      <div className="wizard-step__header">
        <span className="wizard-step__number">1</span>
        <div>
          <h2 className="wizard-step__title">Project Information</h2>
          <p className="wizard-step__subtitle">
            Enter basic project details before starting the AI-guided research setup.
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
            onChange={(e) => setClientName(e.target.value)}
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
            onChange={(e) => setProjectName(e.target.value)}
          />
          <span className="wizard-field__hint">
            A descriptive name to identify this research project
          </span>
        </div>

        {/* AI Guidance Preview */}
        <div className="wizard-field">
          <div className="wizard-ai-preview">
            <div className="wizard-ai-preview__icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div className="wizard-ai-preview__content">
              <h4>Next: AI Context Guide</h4>
              <p>
                You'll have a conversation with our AI assistant to define your research scope. 
                Through natural dialogue, we'll generate your investment thesis, KPIs, and value chain segments.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="wizard-step__nav">
        <button className="wizard-btn wizard-btn--ghost" onClick={onCancel}>
          Cancel
        </button>
        <button 
          className="wizard-btn wizard-btn--primary"
          onClick={handleSetupComplete}
          disabled={!clientName.trim() || !projectName.trim()}
        >
          Start Conversation
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );

  // For chat step, render the ChatWizard full-screen
  if (currentStep === 'chat') {
    return (
      <ChatWizard
        projectId={projectId || undefined}
        clientName={clientName}
        projectName={projectName}
        onComplete={handleChatComplete}
        onBack={() => goToStep('setup')}
      />
    );
  }

  return (
    <div className="wizard">
      {/* Header */}
      <div className="wizard__header">
        <h1 className="wizard__title">New Research Project</h1>
        <button className="wizard__close" onClick={onCancel}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Progress */}
      <div className="wizard__progress">
        {steps.map((step, index) => (
          <div 
            key={step.id}
            className={`wizard__progress-step ${
              index < currentStepIndex ? 'wizard__progress-step--completed' :
              index === currentStepIndex ? 'wizard__progress-step--active' : ''
            }`}
          >
            <div className="wizard__progress-number">
              {index < currentStepIndex ? (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 7l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                index + 1
              )}
            </div>
            <span className="wizard__progress-label">{step.label}</span>
            {index < steps.length - 1 && <div className="wizard__progress-line" />}
          </div>
        ))}
      </div>

      {/* Content */}
      <div className="wizard__content">
        {currentStep === 'setup' && renderSetupStep()}

        {currentStep === 'framework' && (
          <FrameworkStep
            framework={framework}
            isLoading={false}
            onThesisChange={handleThesisChange}
            onKPIsChange={handleKPIsChange}
            onValueChainChange={handleValueChainChange}
            onBack={() => goToStep('chat')}
            onNext={handleStartDiscovery}
          />
        )}
      </div>
    </div>
  );
}
