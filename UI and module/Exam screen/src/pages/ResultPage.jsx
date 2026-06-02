import { useLocation, useNavigate } from 'react-router-dom';

export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const data = location.state;

  // Format time spent
  const formatTimeSpent = (seconds) => {
    if (!seconds) return '---';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m} phút ${s} giây`;
  };

  // Format submission time
  const formatSubmitTime = (isoString) => {
    if (!isoString) return '---';
    const d = new Date(isoString);
    return d.toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <div className="result-page">
      <div className="result-container glass-card">
        <div className="result-icon">✅</div>
        <h1 className="result-title">Đã nộp bài thành công!</h1>
        <p className="result-message">
          Bài thi của bạn đã được ghi nhận. Kết quả sẽ được thông báo sau bởi giám thị.
          <br />Cảm ơn bạn đã tham gia kỳ thi.
        </p>

        {data && (
          <div className="result-info">
            <div className="result-info-row">
              <span className="label">Bài thi</span>
              <span className="value">{data.examTitle || '---'}</span>
            </div>
            <div className="result-info-row">
              <span className="label">Số câu đã trả lời</span>
              <span className="value">{data.answeredCount || 0} / {data.totalQuestions || 0}</span>
            </div>
            <div className="result-info-row">
              <span className="label">Thời gian làm bài</span>
              <span className="value">{formatTimeSpent(data.timeSpent)}</span>
            </div>
            <div className="result-info-row">
              <span className="label">Thời gian nộp</span>
              <span className="value">{formatSubmitTime(data.submittedAt)}</span>
            </div>
          </div>
        )}

        <button
          className="btn-primary"
          onClick={() => navigate('/exams')}
          style={{ width: '100%' }}
          id="back-to-exams-btn"
        >
          Quay về trang chủ
        </button>
      </div>
    </div>
  );
}
