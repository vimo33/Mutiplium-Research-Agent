import { ReactNode } from 'react';
import './Tag.css';

interface TagProps {
  children: ReactNode;
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
  size?: 'sm' | 'md';
  icon?: ReactNode;
  onRemove?: () => void;
  className?: string;
}

export function Tag({
  children,
  variant = 'default',
  size = 'md',
  icon,
  onRemove,
  className = '',
}: TagProps) {
  const classes = [
    'tag',
    `tag--${variant}`,
    `tag--${size}`,
    onRemove && 'tag--removable',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes}>
      {icon && <span className="tag__icon">{icon}</span>}
      <span className="tag__label">{children}</span>
      {onRemove && (
        <button
          type="button"
          className="tag__remove"
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

// Segment-specific tag with color coding
interface SegmentTagProps {
  segment: string;
  size?: 'sm' | 'md';
  className?: string;
}

const SEGMENT_COLORS: Record<string, string> = {
  'Viticulture': 'success',
  'Grape Production': 'success',
  'Vinification': 'primary',
  'Wine Production': 'primary',
  'Packaging': 'info',
  'Distribution': 'warning',
  'Logistics': 'warning',
  'Retail': 'danger',
  'Sales': 'danger',
  'Marketing': 'default',
  'Branding': 'default',
  'Consumption': 'info',
  'Recycling': 'success',
  'Aftermarket': 'success',
  'Cross-Cutting': 'primary',
};

export function SegmentTag({ segment, size = 'sm', className = '' }: SegmentTagProps) {
  // Find the best matching color
  const colorKey = Object.keys(SEGMENT_COLORS).find(key => 
    segment.toLowerCase().includes(key.toLowerCase())
  );
  const variant = (colorKey ? SEGMENT_COLORS[colorKey] : 'default') as TagProps['variant'];
  
  // Clean up segment name for display
  const displayName = segment
    .replace(/^\d+\.\s*/, '') // Remove leading numbers
    .replace(/\s*\([^)]*\)/, ''); // Remove parenthetical

  return (
    <Tag variant={variant} size={size} className={className}>
      {displayName}
    </Tag>
  );
}

// Country tag with flag
interface CountryTagProps {
  country: string;
  size?: 'sm' | 'md';
  className?: string;
}

const COUNTRY_FLAGS: Record<string, string> = {
  'United States': '🇺🇸',
  'USA': '🇺🇸',
  'France': '🇫🇷',
  'Italy': '🇮🇹',
  'Spain': '🇪🇸',
  'Germany': '🇩🇪',
  'Australia': '🇦🇺',
  'Chile': '🇨🇱',
  'Argentina': '🇦🇷',
  'Portugal': '🇵🇹',
  'New Zealand': '🇳🇿',
  'South Africa': '🇿🇦',
  'Israel': '🇮🇱',
  'Switzerland': '🇨🇭',
  'United Kingdom': '🇬🇧',
  'UK': '🇬🇧',
  'Austria': '🇦🇹',
  'Belgium': '🇧🇪',
  'Netherlands': '🇳🇱',
  'Canada': '🇨🇦',
};

export function CountryTag({ country, size = 'sm', className = '' }: CountryTagProps) {
  const flag = Object.entries(COUNTRY_FLAGS).find(([key]) => 
    country?.toLowerCase().includes(key.toLowerCase())
  )?.[1] || '🌍';
  
  const displayCountry = country?.replace(/\s*\([^)]*\)/, '').trim() || 'Unknown';

  return (
    <Tag variant="default" size={size} className={className}>
      <span style={{ marginRight: '4px' }}>{flag}</span>
      {displayCountry}
    </Tag>
  );
}


