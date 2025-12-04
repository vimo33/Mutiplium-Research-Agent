import { InputHTMLAttributes, forwardRef, ReactNode } from 'react';
import './Checkbox.css';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: ReactNode;
  description?: string;
  indeterminate?: boolean;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, description, indeterminate = false, className = '', id, ...props }, ref) => {
    const checkboxId = id || `checkbox-${Math.random().toString(36).slice(2, 9)}`;

    const wrapperClasses = [
      'checkbox-wrapper',
      props.disabled && 'checkbox-wrapper--disabled',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div className={wrapperClasses}>
        <div className="checkbox-container">
          <input
            ref={ref}
            type="checkbox"
            id={checkboxId}
            className="checkbox-input"
            data-indeterminate={indeterminate}
            {...props}
          />
          <div className="checkbox-box">
            {indeterminate ? (
              <svg className="checkbox-icon" viewBox="0 0 12 12" fill="none">
                <path
                  d="M2.5 6H9.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg className="checkbox-icon" viewBox="0 0 12 12" fill="none">
                <path
                  d="M2.5 6L5 8.5L9.5 3.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        </div>
        {(label || description) && (
          <div className="checkbox-content">
            {label && (
              <label htmlFor={checkboxId} className="checkbox-label">
                {label}
              </label>
            )}
            {description && (
              <span className="checkbox-description">{description}</span>
            )}
          </div>
        )}
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';

// Toggle Switch variant
interface ToggleProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  label?: ReactNode;
  size?: 'sm' | 'md';
}

export const Toggle = forwardRef<HTMLInputElement, ToggleProps>(
  ({ label, size = 'md', className = '', id, ...props }, ref) => {
    const toggleId = id || `toggle-${Math.random().toString(36).slice(2, 9)}`;

    const wrapperClasses = [
      'toggle-wrapper',
      `toggle-wrapper--${size}`,
      props.disabled && 'toggle-wrapper--disabled',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div className={wrapperClasses}>
        <div className="toggle-container">
          <input
            ref={ref}
            type="checkbox"
            id={toggleId}
            className="toggle-input"
            {...props}
          />
          <div className="toggle-track">
            <div className="toggle-thumb" />
          </div>
        </div>
        {label && (
          <label htmlFor={toggleId} className="toggle-label">
            {label}
          </label>
        )}
      </div>
    );
  }
);

Toggle.displayName = 'Toggle';

