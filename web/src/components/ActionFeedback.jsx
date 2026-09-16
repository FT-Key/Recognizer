export function ActionFeedback({ feedback }) {
  return (
    <div className={`action-feedback ${feedback ? 'action-feedback--visible' : ''}`}>
      {feedback ? `${feedback.emoji} ${feedback.label}` : ''}
    </div>
  );
}
