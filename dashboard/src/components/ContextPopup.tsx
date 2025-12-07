import { useState, useEffect, useRef } from 'react';
import { Button } from './ui';
import './ContextPopup.css';

type ContextType = 'thesis' | 'kpis' | 'valueChain' | 'brief';

interface ContextPopupProps {
  type: ContextType;
  title: string;
  content: string | string[] | { name: string; target?: string; rationale?: string }[] | { segment: string; description?: string }[];
  onClose: () => void;
}

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 4l12 12M16 4L4 16" strokeLinecap="round" />
  </svg>
);

const CopyIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="5" y="5" width="9" height="9" rx="1" />
    <path d="M11 5V3a1 1 0 00-1-1H3a1 1 0 00-1 1v7a1 1 0 001 1h2" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 8l4 4 6-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function formatContent(type: ContextType, content: ContextPopupProps['content']): string {
  if (typeof content === 'string') {
    return content || 'Not defined';
  }

  if (Array.isArray(content)) {
    if (content.length === 0) return 'Not defined';

    // KPIs format
    if (type === 'kpis' && typeof content[0] === 'object' && 'name' in content[0]) {
      return (content as { name: string; target?: string; rationale?: string }[])
        .map((kpi, i) => `${i + 1}. **${kpi.name}**${kpi.target ? `\n   Target: ${kpi.target}` : ''}${kpi.rationale ? `\n   Rationale: ${kpi.rationale}` : ''}`)
        .join('\n\n');
    }

    // Value Chain format
    if (type === 'valueChain' && typeof content[0] === 'object' && 'segment' in content[0]) {
      return (content as { segment: string; description?: string }[])
        .map((vc, i) => `${i + 1}. **${vc.segment}**${vc.description ? `\n   ${vc.description}` : ''}`)
        .join('\n\n');
    }

    // String array
    return content.join('\n');
  }

  return 'Not defined';
}

function getPlainText(type: ContextType, content: ContextPopupProps['content']): string {
  if (typeof content === 'string') {
    return content || 'Not defined';
  }

  if (Array.isArray(content)) {
    if (content.length === 0) return 'Not defined';

    // KPIs format
    if (type === 'kpis' && typeof content[0] === 'object' && 'name' in content[0]) {
      return (content as { name: string; target?: string; rationale?: string }[])
        .map((kpi, i) => `${i + 1}. ${kpi.name}${kpi.target ? ` - Target: ${kpi.target}` : ''}${kpi.rationale ? ` (${kpi.rationale})` : ''}`)
        .join('\n');
    }

    // Value Chain format
    if (type === 'valueChain' && typeof content[0] === 'object' && 'segment' in content[0]) {
      return (content as { segment: string; description?: string }[])
        .map((vc, i) => `${i + 1}. ${vc.segment}${vc.description ? ` - ${vc.description}` : ''}`)
        .join('\n');
    }

    // String array
    return content.join('\n');
  }

  return 'Not defined';
}

export function ContextPopup({ type, title, content, onClose }: ContextPopupProps) {
  const [copied, setCopied] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Close on click outside
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleCopy = async () => {
    const text = getPlainText(type, content);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const formattedContent = formatContent(type, content);

  return (
    <div className="context-popup-overlay" onClick={handleOverlayClick}>
      <div className="context-popup" ref={popupRef}>
        <div className="context-popup__header">
          <h2 className="context-popup__title">{title}</h2>
          <div className="context-popup__actions">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className={copied ? 'context-popup__copy--success' : ''}
            >
              {copied ? <CheckIcon /> : <CopyIcon />}
              {copied ? 'Copied!' : 'Copy'}
            </Button>
            <button className="context-popup__close" onClick={onClose}>
              <CloseIcon />
            </button>
          </div>
        </div>
        <div className="context-popup__content">
          {formattedContent.split('\n').map((line, i) => {
            // Handle bold text
            const parts = line.split(/\*\*(.*?)\*\*/g);
            return (
              <p key={i} className={line.startsWith('   ') ? 'context-popup__indent' : ''}>
                {parts.map((part, j) => 
                  j % 2 === 1 ? <strong key={j}>{part}</strong> : part
                )}
              </p>
            );
          })}
        </div>
      </div>
    </div>
  );
}

