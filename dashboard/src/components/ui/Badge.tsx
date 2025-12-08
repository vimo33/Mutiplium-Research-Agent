import { ReactNode } from 'react';
import './Badge.css';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
  size?: 'sm' | 'md' | 'lg' | string;
  dot?: boolean;
  onRemove?: () => void;
  className?: string;
}

export function Badge({
  children,
  variant = 'default',
  dot = false,
  onRemove,
  className = '',
}: BadgeProps) {
  const classes = [
    'badge',
    `badge--${variant}`,
    dot && 'badge--dot',
    onRemove && 'badge--removable',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes}>
      {dot && <span className="badge__dot" />}
      {children}
      {onRemove && (
        <button
          type="button"
          className="badge__remove"
          onClick={onRemove}
          aria-label="Remove"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M9 3L3 9M3 3L9 9"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </span>
  );
}

// Status badge for company research status
interface StatusBadgeProps {
  status: 'completed' | 'pending' | 'in_progress' | 'failed' | string;
  className?: string;
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const normalized = status.toLowerCase().replace(/[_-]/g, '');
  
  let variant: BadgeProps['variant'] = 'default';
  let label = status;
  
  switch (normalized) {
    case 'completed':
      variant = 'success';
      label = 'Completed';
      break;
    case 'pending':
      variant = 'warning';
      label = 'Pending';
      break;
    case 'inprogress':
    case 'running':
      variant = 'primary';
      label = 'In Progress';
      break;
    case 'failed':
    case 'error':
      variant = 'danger';
      label = 'Failed';
      break;
    default:
      label = status.charAt(0).toUpperCase() + status.slice(1);
  }

  return (
    <Badge variant={variant} dot className={className}>
      {label}
    </Badge>
  );
}

// Confidence badge with color scale
interface ConfidenceBadgeProps {
  confidence: number; // 0 to 1
  showPercent?: boolean;
  className?: string;
}

export function ConfidenceBadge({ 
  confidence, 
  showPercent = true,
  className = '' 
}: ConfidenceBadgeProps) {
  let variant: BadgeProps['variant'] = 'default';
  
  if (confidence >= 0.8) {
    variant = 'success';
  } else if (confidence >= 0.6) {
    variant = 'warning';
  } else {
    variant = 'danger';
  }

  const percent = Math.round(confidence * 100);

  return (
    <Badge variant={variant} className={className}>
      {showPercent ? `${percent}%` : `${percent}% confidence`}
    </Badge>
  );
}

