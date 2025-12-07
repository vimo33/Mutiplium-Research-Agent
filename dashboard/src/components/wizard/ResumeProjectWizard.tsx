import { useState, useCallback, useEffect } from 'react';
import type { 
  Project, 
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

// Start discovery API call
async function startDiscoveryRun(projectId: string, framework: ResearchFramework): Promise<boolean> {
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
    return response.ok;
  } catch (err) {
    console.error('Error starting discovery:', err);
    return false;
  }
}

type WizardStep = 'chat' | 'framework';

interface ResumeProjectWizardProps {
  project: Project;
  onComplete: (project: Partial<Project>) => void;
  onCancel: () => void;
}

// Progress steps config
const steps: { id: WizardStep; label: string }[] = [
  { id: 'chat', label: 'Context Guide' },
  { id: 'framework', label: 'Review & Launch' },
];

export function ResumeProjectWizard({ project, onComplete, onCancel }: ResumeProjectWizardProps) {
  // Determine starting step based on existing data
  const [currentStep, setCurrentStep] = useState<WizardStep>(() => {
    // If we have a framework with thesis, KPIs and value chain, go to framework review
    if (
      project.framework?.thesis &&
      project.framework?.kpis?.length >= 3 &&
      project.framework?.valueChain?.length >= 3
    ) {
      return 'framework';
    }
    // Otherwise start/resume chat
    return 'chat';
  });
  
  // Brief summary from chat
  const [briefSummary, setBriefSummary] = useState(project.brief?.objective || '');
  
  // Framework (start with existing or empty)
  const [framework, setFramework] = useState<ResearchFramework>(
    project.framework || {
      thesis: '',
      kpis: [],
      valueChain: [],
    }
  );

  // Check for saved chat artifacts on mount
  useEffect(() => {
    const loadSavedArtifacts = async () => {
      try {
        const response = await fetch(`${API_BASE}/projects/${project.id}/chat/load`);
        if (response.ok) {
          const data = await response.json();
          if (data.found && data.artifacts) {
            // Update framework with saved artifacts if we have them
            const savedArtifacts = data.artifacts;
            if (savedArtifacts.thesis || savedArtifacts.kpis?.length || savedArtifacts.value_chain?.length) {
              setFramework({
                thesis: savedArtifacts.thesis || framework.thesis,
                kpis: savedArtifacts.kpis || framework.kpis,
                valueChain: savedArtifacts.value_chain || framework.valueChain,
              });
            }
          }
        }
      } catch (err) {
        console.error('Failed to load saved artifacts:', err);
      }
    };

    loadSavedArtifacts();
  }, [project.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Step navigation
  const goToStep = (step: WizardStep) => setCurrentStep(step);

  // Handle chat completion
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

  // Handle framework completion - start discovery
  const handleStartDiscovery = async () => {
    // Start the discovery run
    await startDiscoveryRun(project.id, framework);

    onComplete({
      brief: {
        ...project.brief,
        objective: briefSummary || framework.thesis.slice(0, 500),
      },
      framework,
      status: 'researching',
    });
  };

  // Get current step index
  const currentStepIndex = steps.findIndex(s => s.id === currentStep);

  // For chat step, render the ChatWizard full-screen
  if (currentStep === 'chat') {
    return (
      <ChatWizard
        projectId={project.id}
        clientName={project.clientName}
        projectName={project.projectName}
        onComplete={handleChatComplete}
        onBack={onCancel}
      />
    );
  }

  return (
    <div className="wizard">
      {/* Header */}
      <div className="wizard__header">
        <h1 className="wizard__title">Resume: {project.projectName}</h1>
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

