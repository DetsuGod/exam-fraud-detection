export default function QuestionCard({ question, index, selectedAnswer, onSelectAnswer }) {
  const labels = ['A', 'B', 'C', 'D'];

  return (
    <div 
      className="question-card glass-card" 
      style={{ animationDelay: `${Math.min(index * 0.05, 0.5)}s` }}
      id={`question-${question.id}`}
    >
      {/* Hiển thị đoạn văn nếu có */}
      {question.passage && (
        <div 
          className="reading-passage-container"
          dangerouslySetInnerHTML={{ __html: question.passage }} 
        />
      )}

      <div className="question-header">
        <span className="question-number">{question.id}</span>
        <div className="question-text" dangerouslySetInnerHTML={{ __html: question.question }} />
      </div>
      <div className="options-list">
        {question.options.map((option, optIndex) => (
          <div
            key={optIndex}
            className={`option-item ${selectedAnswer === optIndex ? 'selected' : ''}`}
            onClick={() => onSelectAnswer(question.id, optIndex)}
          >
            <div className="option-label">{labels[optIndex]}</div>
            <div 
              className="option-text"
              dangerouslySetInnerHTML={{ __html: option }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
