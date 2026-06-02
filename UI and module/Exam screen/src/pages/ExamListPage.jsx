import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import examData from '../data/examData';

export default function ExamListPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    // Stop camera and screen streams
    if (window.__examCameraStream) {
      window.__examCameraStream.getTracks().forEach(t => t.stop());
      window.__examCameraStream = null;
    }
    if (window.__examScreenStream) {
      window.__examScreenStream.getTracks().forEach(t => t.stop());
      window.__examScreenStream = null;
    }
    logout();
    navigate('/login');
  };

  const handleStartExam = (examId) => {
    navigate(`/exam/${examId}`);
  };

  return (
    <div className="exam-list-page">
      {/* Header */}
      <header className="page-header">
        <div className="header-brand">
          <span className="brand-kanji">日本語試験</span>
        </div>
        <div className="header-user">
          <span className="user-name">
            👤 {user?.name || 'Thí sinh'}
          </span>
          <button className="btn-logout" onClick={handleLogout} id="logout-btn">
            Đăng xuất
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="exam-list-content">
        <h1 className="exam-list-title">選択してください</h1>
        <p className="exam-list-subtitle">
          Chọn bài thi bên dưới để bắt đầu. Hãy đảm bảo bạn đã sẵn sàng trước khi bắt đầu.
        </p>

        <div className="exam-grid">
          {examData.map((exam) => (
            <div
              key={exam.id}
              className="exam-card glass-card"
              onClick={() => handleStartExam(exam.id)}
              id={`exam-card-${exam.id}`}
            >
              <span className="exam-level">{exam.level}</span>
              <h2 className="exam-title">{exam.title}</h2>
              <p className="exam-desc">{exam.description}</p>
              <div className="exam-meta">
                <span>📝 {exam.totalQuestions} câu hỏi</span>
                <span>⏱️ {exam.duration} phút</span>
              </div>
              <div className="start-label">
                <span>Bắt đầu làm bài</span>
                <span className="arrow">→</span>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
