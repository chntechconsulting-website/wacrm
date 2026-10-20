import React from 'react';
import PingoMascot from './PingoMascot';
import './PingoEmptyState.css';

/**
 * PingoEmptyState
 * Replaces dry blank states with a warm, branded Pingo experience.
 */
const PingoEmptyState = ({
  pose = 'playful',
  height = 140,
  title = 'No Records Found',
  description = 'There are no items to display at this moment.',
  actionLabel,
  onAction,
  actionIcon: ActionIcon,
  secondaryActionLabel,
  onSecondaryAction,
  className = '',
  compact = false
}) => {
  return (
    <div className={`pingo-empty-state ${compact ? 'pingo-empty-compact' : ''} ${className}`}>
      <div className="pingo-empty-mascot">
        <PingoMascot pose={pose} height={height} withShadow={true} />
      </div>
      <div className="pingo-empty-content">
        <h3 className="pingo-empty-title">{title}</h3>
        {description && <p className="pingo-empty-desc">{description}</p>}
        {(actionLabel || secondaryActionLabel) && (
          <div className="pingo-empty-actions">
            {secondaryActionLabel && onSecondaryAction && (
              <button
                type="button"
                className="btn btn-secondary pingo-empty-btn"
                onClick={onSecondaryAction}
              >
                {secondaryActionLabel}
              </button>
            )}
            {actionLabel && onAction && (
              <button
                type="button"
                className="btn btn-primary pingo-empty-btn"
                onClick={onAction}
              >
                {ActionIcon && <ActionIcon size={16} />}
                <span>{actionLabel}</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PingoEmptyState;
