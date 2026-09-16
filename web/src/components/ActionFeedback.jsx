import { Icon } from '../lib/icons.jsx';

export function ActionFeedback({ feedback }) {
  return (
    <div
      className={`action-feedback ${feedback ? 'action-feedback--visible' : ''}`}
      role="status"
      aria-live="polite"
    >
      {feedback ? (
        <>
          <Icon name={feedback.icon} size={16} /> {feedback.label}
        </>
      ) : (
        ''
      )}
    </div>
  );
}
