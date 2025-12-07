import { useState, useRef, useEffect, useCallback } from 'react';
import { useChat, cleanContentForDisplay } from '../../hooks';
import type { ChatMessage, ChatArtifacts } from '../../hooks';
import { Button } from '../ui';
import { ArtifactCard } from './ArtifactCard';
import './ChatWizard.css';

interface ChatWizardProps {
  projectId?: string;
  clientName: string;
  projectName: string;
  onComplete: (artifacts: ChatArtifacts, briefSummary: string) => void;
  onBack: () => void;
}

// Typing indicator component
function TypingIndicator() {
  return (
    <div className="chat-typing">
      <div className="chat-typing__dot" />
      <div className="chat-typing__dot" />
      <div className="chat-typing__dot" />
    </div>
  );
}

// Parse and render message content with inline artifacts
function MessageContent({ content, artifacts }: { content: string; artifacts?: ChatArtifacts }) {
  // Clean content for display (removes markers, formats nicely)
  const cleanContent = cleanContentForDisplay(content);

  // Split content into paragraphs for better rendering
  const paragraphs = cleanContent.split('\n\n').filter(p => p.trim());

  return (
    <div className="chat-message__content">
      {paragraphs.map((paragraph, idx) => (
        <p key={idx} className="chat-message__paragraph">
          {paragraph.split('\n').map((line, lineIdx) => (
            <span key={lineIdx}>
              {lineIdx > 0 && <br />}
              {renderFormattedText(line)}
            </span>
          ))}
        </p>
      ))}
      
      {/* Render artifact cards if present */}
      {artifacts && (artifacts.thesis || artifacts.kpis.length > 0 || artifacts.valueChain.length > 0) && (
        <div className="chat-message__artifacts">
          {artifacts.thesis && (
            <ArtifactCard
              type="thesis"
              title="Investment Thesis"
              content={artifacts.thesis}
            />
          )}
          {artifacts.kpis.length > 0 && (
            <ArtifactCard
              type="kpis"
              title={`Key Performance Indicators (${artifacts.kpis.length})`}
              items={artifacts.kpis}
            />
          )}
          {artifacts.valueChain.length > 0 && (
            <ArtifactCard
              type="valueChain"
              title={`Value Chain Segments (${artifacts.valueChain.length})`}
              items={artifacts.valueChain}
            />
          )}
        </div>
      )}
    </div>
  );
}

// Render formatted text (bold, etc.)
function renderFormattedText(text: string): React.ReactNode {
  // Handle bold text with **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    }
    // Handle bullet points
    if (part.startsWith('• ')) {
      return <span key={idx} className="chat-bullet">{part}</span>;
    }
    return part;
  });
}

// Single message component
function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`chat-message chat-message--${message.role}`}>
      <div className="chat-message__avatar">
        {isUser ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="8" r="4" />
            <path d="M20 21a8 8 0 1 0-16 0" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        )}
      </div>
      <div className="chat-message__bubble">
        {isUser ? (
          <p className="chat-message__text">{message.content}</p>
        ) : (
          <MessageContent content={message.content} artifacts={message.artifacts} />
        )}
        <span className="chat-message__time">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}

export function ChatWizard({ projectId, clientName, projectName, onComplete, onBack }: ChatWizardProps) {
  const {
    messages,
    isStreaming,
    error,
    artifacts,
    isLoading,
    sendMessage,
    resetChat,
    finalizeChat,
    loadChat,
    saveChat,
  } = useChat(projectId, clientName, projectName);

  const [inputValue, setInputValue] = useState('');
  const [isReady, setIsReady] = useState(false);
  const [hasLoadedChat, setHasLoadedChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load existing chat on mount
  useEffect(() => {
    if (projectId && !hasLoadedChat) {
      loadChat().then((loaded) => {
        setHasLoadedChat(true);
        // If no existing chat, send initial greeting
        if (!loaded) {
          sendMessage('Hi, I\'d like to set up a new research project.');
        }
      });
    } else if (!projectId && !hasLoadedChat) {
      setHasLoadedChat(true);
      // No projectId, send initial greeting
      sendMessage('Hi, I\'d like to set up a new research project.');
    }
  }, [projectId, hasLoadedChat, loadChat, sendMessage]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  // Focus input on mount
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  // Check if we have enough artifacts to proceed
  useEffect(() => {
    const hasThesis = !!artifacts.thesis;
    const hasKpis = artifacts.kpis.length >= 3;
    const hasValueChain = artifacts.valueChain.length >= 3;
    setIsReady(hasThesis && hasKpis && hasValueChain);
  }, [artifacts]);

  // Save chat before leaving
  useEffect(() => {
    const handleBeforeUnload = () => {
      saveChat();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Save on unmount too
      saveChat();
    };
  }, [saveChat]);

  // Handle form submission
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !isStreaming) {
      sendMessage(inputValue.trim());
      setInputValue('');
    }
  }, [inputValue, isStreaming, sendMessage]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit]);

  // Handle completion
  const handleComplete = useCallback(async () => {
    const finalArtifacts = await finalizeChat();
    if (finalArtifacts) {
      // Create brief summary from first user messages
      const userMessages = messages.filter(m => m.role === 'user');
      const briefSummary = userMessages.slice(0, 3).map(m => m.content).join(' ').slice(0, 500);
      onComplete(finalArtifacts, briefSummary);
    }
  }, [finalizeChat, messages, onComplete]);

  // Handle back with save
  const handleBack = useCallback(async () => {
    await saveChat();
    onBack();
  }, [saveChat, onBack]);

  // Suggestion prompts for users
  const suggestions = [
    "Tell me about your investment focus",
    "What sectors interest you most?",
    "Describe your ideal target company",
    "What's your geographic preference?",
  ];

  // Show loading state while loading chat history
  if (isLoading) {
    return (
      <div className="chat-wizard">
        <div className="chat-wizard__header">
          <div className="chat-wizard__header-content">
            <button className="chat-wizard__back" onClick={onBack}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <div className="chat-wizard__header-info">
              <h2 className="chat-wizard__title">Research Context Guide</h2>
              <p className="chat-wizard__subtitle">Loading your conversation...</p>
            </div>
          </div>
        </div>
        <div className="chat-wizard__messages">
          <div className="chat-wizard__welcome">
            <div className="chat-wizard__welcome-icon">
              <div className="wizard-loading__spinner" />
            </div>
            <h3>Loading previous conversation...</h3>
            <p>Please wait while we restore your progress.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-wizard">
      {/* Header */}
      <div className="chat-wizard__header">
        <div className="chat-wizard__header-content">
          <button className="chat-wizard__back" onClick={handleBack}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <div className="chat-wizard__header-info">
            <h2 className="chat-wizard__title">Research Context Guide</h2>
            <p className="chat-wizard__subtitle">
              {clientName && projectName 
                ? `${projectName} for ${clientName}`
                : 'Chat with AI to define your research scope'
              }
            </p>
          </div>
        </div>
        
        {/* Progress indicator */}
        <div className="chat-wizard__progress">
          <div className={`chat-wizard__progress-item ${artifacts.thesis ? 'chat-wizard__progress-item--complete' : ''}`}>
            <span className="chat-wizard__progress-icon">
              {artifacts.thesis ? '✓' : '○'}
            </span>
            <span>Thesis</span>
          </div>
          <div className={`chat-wizard__progress-item ${artifacts.kpis.length >= 3 ? 'chat-wizard__progress-item--complete' : ''}`}>
            <span className="chat-wizard__progress-icon">
              {artifacts.kpis.length >= 3 ? '✓' : '○'}
            </span>
            <span>KPIs ({artifacts.kpis.length})</span>
          </div>
          <div className={`chat-wizard__progress-item ${artifacts.valueChain.length >= 3 ? 'chat-wizard__progress-item--complete' : ''}`}>
            <span className="chat-wizard__progress-icon">
              {artifacts.valueChain.length >= 3 ? '✓' : '○'}
            </span>
            <span>Segments ({artifacts.valueChain.length})</span>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div className="chat-wizard__messages">
        {messages.length === 0 && !hasLoadedChat && (
          <div className="chat-wizard__welcome">
            <div className="chat-wizard__welcome-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <h3>Welcome to Research Setup</h3>
            <p>I'll help you define your investment research scope through conversation.</p>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessageBubble key={message.id} message={message} />
        ))}

        {isStreaming && (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message__avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div className="chat-message__bubble">
              <TypingIndicator />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error display */}
      {error && (
        <div className="chat-wizard__error">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          <span>{error}</span>
          <button onClick={() => resetChat()}>Reset Chat</button>
        </div>
      )}

      {/* Suggestions (show only when few messages) */}
      {messages.length > 0 && messages.length < 4 && !isStreaming && (
        <div className="chat-wizard__suggestions">
          {suggestions.map((suggestion, idx) => (
            <button
              key={idx}
              className="chat-wizard__suggestion"
              onClick={() => setInputValue(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <form className="chat-wizard__input-area" onSubmit={handleSubmit}>
        <div className="chat-wizard__input-container">
          <textarea
            ref={inputRef}
            className="chat-wizard__input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your research goals..."
            rows={1}
            disabled={isStreaming}
          />
          <button
            type="submit"
            className="chat-wizard__send"
            disabled={!inputValue.trim() || isStreaming}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* Action buttons */}
        <div className="chat-wizard__actions">
          <Button variant="ghost" onClick={handleBack} disabled={isStreaming}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleComplete}
            disabled={!isReady || isStreaming}
          >
            {isReady ? 'Review Framework' : 'Complete conversation to continue'}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Button>
        </div>
      </form>
    </div>
  );
}
