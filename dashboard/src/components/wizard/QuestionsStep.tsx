import { useState, useEffect } from 'react';
import type { ClarifyingQuestion, ResearchBrief } from '../../types';
import { Button } from '../ui';
import './WizardSteps.css';

interface QuestionsStepProps {
  brief: Partial<ResearchBrief>;
  questions: ClarifyingQuestion[];
  isLoading: boolean;
  onQuestionsGenerated: (questions: ClarifyingQuestion[]) => void;
  onAnswerChange: (questionId: string, answer: string | string[]) => void;
  onBack: () => void;
  onNext: () => void;
}

// Default questions to use if AI generation fails
const defaultQuestions: ClarifyingQuestion[] = [
  {
    id: 'stages',
    question: 'What company stages are you targeting?',
    type: 'multiple_choice',
    options: ['Pre-seed', 'Seed', 'Series A', 'Series B', 'Series C+', 'Growth/PE'],
  },
  {
    id: 'investment_size',
    question: 'What is your target investment size?',
    type: 'single_choice',
    options: ['<€500K', '€500K-€2M', '€2M-€5M', '€5M-€15M', '>€15M'],
  },
  {
    id: 'geography',
    question: 'What geographic regions are you focused on?',
    type: 'multiple_choice',
    options: ['Western Europe', 'UK & Ireland', 'Nordics', 'Southern Europe', 'Eastern Europe', 'North America', 'APAC', 'Global'],
  },
  {
    id: 'business_model',
    question: 'What business models are you interested in?',
    type: 'multiple_choice',
    options: ['B2B SaaS', 'B2C', 'Marketplace', 'Hardware', 'Deep Tech', 'Services'],
  },
  {
    id: 'additional',
    question: 'Any specific technologies, trends, or characteristics you want to focus on?',
    type: 'text',
  },
];

// Check icon
const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 7l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function QuestionsStep({
  brief,
  questions,
  isLoading,
  onQuestionsGenerated,
  onAnswerChange,
  onBack,
  onNext,
}: QuestionsStepProps) {
  const [localQuestions, setLocalQuestions] = useState<ClarifyingQuestion[]>(questions);

  // Use default questions if none provided and not loading
  useEffect(() => {
    if (!isLoading && localQuestions.length === 0) {
      setLocalQuestions(defaultQuestions);
      onQuestionsGenerated(defaultQuestions);
    }
  }, [isLoading, localQuestions.length, onQuestionsGenerated]);

  // Update local state when questions prop changes
  useEffect(() => {
    if (questions.length > 0) {
      setLocalQuestions(questions);
    }
  }, [questions]);

  // Handle answer changes
  const handleSingleChoice = (questionId: string, option: string) => {
    setLocalQuestions(prev => prev.map(q => 
      q.id === questionId ? { ...q, answer: option } : q
    ));
    onAnswerChange(questionId, option);
  };

  const handleMultipleChoice = (questionId: string, option: string) => {
    const question = localQuestions.find(q => q.id === questionId);
    const currentAnswers = (question?.answer as string[]) || [];
    
    const newAnswers = currentAnswers.includes(option)
      ? currentAnswers.filter(a => a !== option)
      : [...currentAnswers, option];
    
    setLocalQuestions(prev => prev.map(q =>
      q.id === questionId ? { ...q, answer: newAnswers } : q
    ));
    onAnswerChange(questionId, newAnswers);
  };

  const handleTextChange = (questionId: string, value: string) => {
    setLocalQuestions(prev => prev.map(q =>
      q.id === questionId ? { ...q, answer: value } : q
    ));
    onAnswerChange(questionId, value);
  };

  // Check if all required questions are answered
  const allAnswered = localQuestions.every(q => {
    if (q.type === 'text') return true; // Text is optional
    if (Array.isArray(q.answer)) return q.answer.length > 0;
    return !!q.answer;
  });

  if (isLoading) {
    return (
      <div className="wizard-step">
        <div className="wizard-loading">
          <div className="wizard-loading__spinner" />
          <p className="wizard-loading__text">
            Analyzing your research brief...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-step">
      <div className="wizard-step__header">
        <span className="wizard-step__number">2</span>
        <div>
          <h2 className="wizard-step__title">Clarifying Questions</h2>
          <p className="wizard-step__subtitle">
            Help us understand your criteria better so we can generate the most 
            relevant investment thesis and value chain for your research.
          </p>
        </div>
      </div>

      <div className="wizard-step__form">
        {localQuestions.map((question) => (
          <div key={question.id} className="wizard-field">
            <label className="wizard-field__label">
              {question.question}
              {question.type !== 'text' && (
                <span className="wizard-field__required">*</span>
              )}
            </label>

            {/* Single Choice */}
            {question.type === 'single_choice' && question.options && (
              <div className="wizard-option-group">
                {question.options.map((option) => (
                  <label
                    key={option}
                    className={`wizard-option ${question.answer === option ? 'wizard-option--selected' : ''}`}
                  >
                    <input
                      type="radio"
                      name={question.id}
                      checked={question.answer === option}
                      onChange={() => handleSingleChoice(question.id, option)}
                    />
                    <span className="wizard-option__check">
                      {question.answer === option && <CheckIcon />}
                    </span>
                    {option}
                  </label>
                ))}
              </div>
            )}

            {/* Multiple Choice */}
            {question.type === 'multiple_choice' && question.options && (
              <div className="wizard-option-group">
                {question.options.map((option) => {
                  const answers = (question.answer as string[]) || [];
                  const isSelected = answers.includes(option);
                  return (
                    <label
                      key={option}
                      className={`wizard-option ${isSelected ? 'wizard-option--selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleMultipleChoice(question.id, option)}
                      />
                      <span className="wizard-option__check">
                        {isSelected && <CheckIcon />}
                      </span>
                      {option}
                    </label>
                  );
                })}
              </div>
            )}

            {/* Text Input */}
            {question.type === 'text' && (
              <textarea
                className="wizard-field__textarea"
                placeholder="Enter your response..."
                value={(question.answer as string) || ''}
                onChange={(e) => handleTextChange(question.id, e.target.value)}
                rows={3}
              />
            )}
          </div>
        ))}
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
          disabled={!allAnswered}
        >
          Generate Framework
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Button>
      </div>
    </div>
  );
}

