import './ProgressRing.css';

interface ProgressRingProps {
  progress: number; // 0 to 100
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showLabel?: boolean;
  className?: string;
}

export function ProgressRing({
  progress,
  size = 'md',
  showLabel = true,
  className = '',
}: ProgressRingProps) {
  const sizes = {
    sm: { diameter: 32, strokeWidth: 4 },
    md: { diameter: 44, strokeWidth: 5 },
    lg: { diameter: 64, strokeWidth: 6 },
    xl: { diameter: 80, strokeWidth: 8 },
  };

  const { diameter, strokeWidth } = sizes[size];
  const radius = (diameter - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  const classes = [
    'progress-ring',
    `progress-ring--${size}`,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      <svg
        width={diameter}
        height={diameter}
        viewBox={`0 0 ${diameter} ${diameter}`}
        className="progress-ring__svg"
      >
        {/* Background track */}
        <circle
          className="progress-ring__track"
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Progress arc */}
        <circle
          className="progress-ring__progress"
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${diameter / 2} ${diameter / 2})`}
        />
      </svg>
      {showLabel && (
        <span className="progress-ring__label">
          {Math.round(progress)}%
        </span>
      )}
    </div>
  );
}

// Confidence ring variant with color coding
interface ConfidenceRingProps {
  confidence: number; // 0 to 1
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export function ConfidenceRing({
  confidence,
  size = 'md',
  showLabel = true,
  className = '',
}: ConfidenceRingProps) {
  const percent = confidence * 100;
  
  let colorClass = 'confidence-ring--low';
  if (confidence >= 0.8) {
    colorClass = 'confidence-ring--high';
  } else if (confidence >= 0.6) {
    colorClass = 'confidence-ring--medium';
  }

  return (
    <div className={`confidence-ring ${colorClass} ${className}`}>
      <ProgressRing progress={percent} size={size} showLabel={showLabel} />
    </div>
  );
}

// SWOT indicator dots
interface SwotDotsProps {
  count: number;
  maxCount?: number;
  variant: 'strength' | 'weakness' | 'opportunity' | 'threat';
  className?: string;
}

export function SwotDots({
  count,
  maxCount = 4,
  variant,
  className = '',
}: SwotDotsProps) {
  const filled = Math.min(count, maxCount);
  const empty = maxCount - filled;

  return (
    <div className={`swot-dots swot-dots--${variant} ${className}`}>
      {Array.from({ length: filled }).map((_, i) => (
        <span key={`filled-${i}`} className="swot-dot swot-dot--filled" />
      ))}
      {Array.from({ length: empty }).map((_, i) => (
        <span key={`empty-${i}`} className="swot-dot swot-dot--empty" />
      ))}
    </div>
  );
}


