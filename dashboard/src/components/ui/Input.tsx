import { InputHTMLAttributes, forwardRef, ReactNode } from 'react';
import './Input.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, leftIcon, rightIcon, className = '', id, ...props }, ref) => {
    const inputId = id || `input-${Math.random().toString(36).slice(2, 9)}`;
    
    const wrapperClasses = [
      'input-wrapper',
      error && 'input-wrapper--error',
      props.disabled && 'input-wrapper--disabled',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div className={wrapperClasses}>
        {label && (
          <label htmlFor={inputId} className="input-label">
            {label}
          </label>
        )}
        <div className="input-container">
          {leftIcon && <span className="input-icon input-icon--left">{leftIcon}</span>}
          <input
            ref={ref}
            id={inputId}
            className={`input ${leftIcon ? 'input--has-left-icon' : ''} ${rightIcon ? 'input--has-right-icon' : ''}`}
            {...props}
          />
          {rightIcon && <span className="input-icon input-icon--right">{rightIcon}</span>}
        </div>
        {error && <span className="input-error">{error}</span>}
        {hint && !error && <span className="input-hint">{hint}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';

// Search-specific input
interface SearchInputProps extends Omit<InputProps, 'leftIcon' | 'type'> {
  onClear?: () => void;
}

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  ({ onClear, value, className = '', ...props }, ref) => {
    const SearchIcon = (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="9" cy="9" r="6" />
        <path d="M13.5 13.5L17 17" strokeLinecap="round" />
      </svg>
    );

    const ClearButton = value ? (
      <button
        type="button"
        className="input-clear"
        onClick={onClear}
        aria-label="Clear search"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 4L4 12M4 4L12 12" strokeLinecap="round" />
        </svg>
      </button>
    ) : undefined;

    return (
      <Input
        ref={ref}
        type="search"
        leftIcon={SearchIcon}
        rightIcon={ClearButton}
        value={value}
        className={`search-input ${className}`}
        {...props}
      />
    );
  }
);

SearchInput.displayName = 'SearchInput';


