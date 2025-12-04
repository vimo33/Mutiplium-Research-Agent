import { useState, useCallback } from 'react';
import type { 
  Project, 
  ResearchBrief, 
  ResearchFramework, 
  ClarifyingQuestion,
  KPI,
  ValueChainSegment,
  TestRunCompany 
} from '../../types';
import { BriefStep } from './BriefStep';
import { QuestionsStep } from './QuestionsStep';
import { FrameworkStep } from './FrameworkStep';
import { TestRunStep } from './TestRunStep';
import { Button } from '../ui';
import './NewResearchWizard.css';

type WizardStep = 'brief' | 'questions' | 'framework' | 'test_run';

interface NewResearchWizardProps {
  onComplete: (project: Partial<Project>) => void;
  onCancel: () => void;
}

// Progress steps config
const steps: { id: WizardStep; label: string }[] = [
  { id: 'brief', label: 'Research Brief' },
  { id: 'questions', label: 'Clarify' },
  { id: 'framework', label: 'Framework' },
  { id: 'test_run', label: 'Test Run' },
];

// Mock AI-generated framework (in production, this comes from GPT)
function generateMockFramework(brief: ResearchBrief, answers: Record<string, any>): ResearchFramework {
  // Extract geography for context
  const geography = answers.geography || ['Europe'];
  const stages = answers.stages || ['Seed', 'Series A'];
  
  return {
    thesis: `This research focuses on identifying innovative companies in the ${brief.objective.split(' ').slice(0, 5).join(' ')}... space. With increasing market demand for sustainable and technology-driven solutions, we see compelling opportunities in ${geography.join(', ')}. Target companies should demonstrate strong product-market fit, defensible technology, and clear paths to scalability within the ${stages.join('/')} stages.`,
    kpis: [
      { name: 'Revenue Growth Rate', target: '>50% YoY', rationale: 'Strong growth indicates market traction' },
      { name: 'Gross Margin', target: '>60%', rationale: 'Software-like margins indicate scalability' },
      { name: 'Customer Retention', target: '>90% annually', rationale: 'High retention validates product value' },
      { name: 'Technology Defensibility', target: 'Patents or proprietary tech', rationale: 'Moat against competition' },
    ],
    valueChain: [
      { segment: 'Production & Operations', description: 'Companies improving core production processes' },
      { segment: 'Supply Chain & Logistics', description: 'Solutions for distribution and logistics optimization' },
      { segment: 'Analytics & Data', description: 'Data-driven insights and decision support' },
      { segment: 'Sustainability & Impact', description: 'Environmental and social impact solutions' },
      { segment: 'Marketing & Sales', description: 'Go-to-market and customer acquisition tools' },
      { segment: 'Quality & Compliance', description: 'Quality assurance and regulatory solutions' },
    ],
  };
}

// Mock test companies (in production, comes from actual test run)
function generateMockTestCompanies(valueChain: ValueChainSegment[]): TestRunCompany[] {
  const mockCompanies = [
    { company: 'TechVine Solutions', segment: 'Production & Operations', country: 'France', confidence_0to1: 0.85 },
    { company: 'GreenGrow AI', segment: 'Production & Operations', country: 'Germany', confidence_0to1: 0.78 },
    { company: 'AgriOptimize', segment: 'Production & Operations', country: 'Netherlands', confidence_0to1: 0.82 },
    { company: 'LogiFlow Systems', segment: 'Supply Chain & Logistics', country: 'UK', confidence_0to1: 0.75 },
    { company: 'ChainTrack Pro', segment: 'Supply Chain & Logistics', country: 'Spain', confidence_0to1: 0.71 },
    { company: 'RouteWise', segment: 'Supply Chain & Logistics', country: 'Italy', confidence_0to1: 0.68 },
    { company: 'DataSense Analytics', segment: 'Analytics & Data', country: 'Germany', confidence_0to1: 0.88 },
    { company: 'InsightHub', segment: 'Analytics & Data', country: 'France', confidence_0to1: 0.79 },
    { company: 'MetricsMaster', segment: 'Analytics & Data', country: 'UK', confidence_0to1: 0.74 },
    { company: 'EcoImpact Labs', segment: 'Sustainability & Impact', country: 'Denmark', confidence_0to1: 0.91 },
    { company: 'GreenMetrics', segment: 'Sustainability & Impact', country: 'Sweden', confidence_0to1: 0.84 },
    { company: 'SustainTech', segment: 'Sustainability & Impact', country: 'Netherlands', confidence_0to1: 0.77 },
    { company: 'MarketBoost', segment: 'Marketing & Sales', country: 'UK', confidence_0to1: 0.72 },
    { company: 'SalesForge', segment: 'Marketing & Sales', country: 'Germany', confidence_0to1: 0.69 },
    { company: 'BrandLift', segment: 'Marketing & Sales', country: 'France', confidence_0to1: 0.65 },
    { company: 'QualityFirst', segment: 'Quality & Compliance', country: 'Switzerland', confidence_0to1: 0.86 },
    { company: 'ComplianceIQ', segment: 'Quality & Compliance', country: 'Germany', confidence_0to1: 0.81 },
    { company: 'CertifyPro', segment: 'Quality & Compliance', country: 'Austria', confidence_0to1: 0.76 },
  ];

  // Filter to only include companies matching the value chain segments
  const segmentNames = valueChain.map(vc => vc.segment);
  return mockCompanies.filter(c => segmentNames.includes(c.segment));
}

export function NewResearchWizard({ onComplete, onCancel }: NewResearchWizardProps) {
  // Current step
  const [currentStep, setCurrentStep] = useState<WizardStep>('brief');
  
  // Brief data
  const [clientName, setClientName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [objective, setObjective] = useState('');
  
  // Brief answers
  const [brief, setBrief] = useState<Partial<ResearchBrief>>({});
  
  // Questions
  const [questions, setQuestions] = useState<ClarifyingQuestion[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  
  // Framework
  const [framework, setFramework] = useState<ResearchFramework>({
    thesis: '',
    kpis: [],
    valueChain: [],
  });
  const [frameworkLoading, setFrameworkLoading] = useState(false);
  
  // Test run
  const [testCompanies, setTestCompanies] = useState<TestRunCompany[]>([]);
  const [testRunLoading, setTestRunLoading] = useState(false);

  // Step navigation
  const goToStep = (step: WizardStep) => setCurrentStep(step);

  // Handle brief completion
  const handleBriefComplete = () => {
    setBrief({ objective });
    setQuestionsLoading(true);
    goToStep('questions');
    
    // Simulate AI generating questions (in production, call backend)
    setTimeout(() => {
      setQuestionsLoading(false);
    }, 1500);
  };

  // Handle questions completion
  const handleQuestionsComplete = () => {
    setFrameworkLoading(true);
    goToStep('framework');
    
    // Generate framework (in production, call GPT)
    setTimeout(() => {
      const generatedFramework = generateMockFramework(
        { ...brief, objective } as ResearchBrief,
        answers
      );
      setFramework(generatedFramework);
      setFrameworkLoading(false);
    }, 2000);
  };

  // Handle framework completion
  const handleFrameworkComplete = () => {
    setTestRunLoading(true);
    goToStep('test_run');
    
    // Run test search (in production, call backend)
    setTimeout(() => {
      const companies = generateMockTestCompanies(framework.valueChain);
      setTestCompanies(companies);
      setTestRunLoading(false);
    }, 3000);
  };

  // Handle answer changes
  const handleAnswerChange = useCallback((questionId: string, answer: string | string[]) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }));
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

  // Handle final approval
  const handleApprove = () => {
    const project: Partial<Project> = {
      clientName,
      projectName,
      brief: {
        objective,
        targetStages: answers.stages || [],
        investmentSize: answers.investment_size || '',
        geography: answers.geography || [],
        technologies: answers.additional ? [answers.additional] : [],
        additionalNotes: '',
      },
      framework,
      status: 'researching',
    };
    onComplete(project);
  };

  // Get current step index
  const currentStepIndex = steps.findIndex(s => s.id === currentStep);

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
        {currentStep === 'brief' && (
          <BriefStep
            clientName={clientName}
            projectName={projectName}
            objective={objective}
            onClientNameChange={setClientName}
            onProjectNameChange={setProjectName}
            onObjectiveChange={setObjective}
            onNext={handleBriefComplete}
          />
        )}

        {currentStep === 'questions' && (
          <QuestionsStep
            brief={brief}
            questions={questions}
            isLoading={questionsLoading}
            onQuestionsGenerated={setQuestions}
            onAnswerChange={handleAnswerChange}
            onBack={() => goToStep('brief')}
            onNext={handleQuestionsComplete}
          />
        )}

        {currentStep === 'framework' && (
          <FrameworkStep
            framework={framework}
            isLoading={frameworkLoading}
            onThesisChange={handleThesisChange}
            onKPIsChange={handleKPIsChange}
            onValueChainChange={handleValueChainChange}
            onBack={() => goToStep('questions')}
            onNext={handleFrameworkComplete}
          />
        )}

        {currentStep === 'test_run' && (
          <TestRunStep
            valueChain={framework.valueChain}
            testCompanies={testCompanies}
            isLoading={testRunLoading}
            onBack={() => goToStep('framework')}
            onApprove={handleApprove}
            onReject={() => goToStep('framework')}
          />
        )}
      </div>
    </div>
  );
}

