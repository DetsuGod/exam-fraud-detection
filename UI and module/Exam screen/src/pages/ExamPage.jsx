import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import examData from '../data/examData';
import QuestionCard from '../components/QuestionCard';
import CameraPreview from '../components/CameraPreview';
import PermissionModal from '../components/PermissionModal';
import useExamMonitor from '../hooks/useExamMonitor';
import { useAuth } from '../context/AuthContext';

export default function ExamPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const exam = examData.find(e => e.id === id);

  const [answers, setAnswers] = useState({});
  const [timeLeft, setTimeLeft] = useState(exam ? exam.duration * 60 : 0);
  const [showConfirm, setShowConfirm] = useState(false);
  const [permissionsGranted, setPermissionsGranted] = useState(
    !!window.__examScreenStream
  );

  // Real-time monitoring hook
  const { wsConnected, violationCount } = useExamMonitor({
    enabled: permissionsGranted,
    studentId: user?.studentId || ''
  });

  // Timer countdown
  useEffect(() => {
    if (timeLeft <= 0) {
      handleAutoSubmit();
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft]);

  // Warn before leaving
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // Monitor media streams status
  const [screenShareActive, setScreenShareActive] = useState(true);
  const [cameraActive, setCameraActive] = useState(true);

  useEffect(() => {
    if (!permissionsGranted) return;

    const checkStream = () => {
      // Check Screen Share
      if (!window.__examScreenStream || window.__examScreenStream.getVideoTracks().length === 0) {
        setScreenShareActive(false);
      } else {
        const track = window.__examScreenStream.getVideoTracks()[0];
        if (track.readyState !== 'live') {
          setScreenShareActive(false);
        } else {
          setScreenShareActive(true);
        }
      }

      // Check Camera
      if (!window.__examCameraStream || window.__examCameraStream.getVideoTracks().length === 0) {
        setCameraActive(false);
      } else {
        const track = window.__examCameraStream.getVideoTracks()[0];
        if (track.readyState !== 'live') {
          setCameraActive(false);
        } else {
          setCameraActive(true);
        }
      }
    };

    const interval = setInterval(checkStream, 1000);
    return () => clearInterval(interval);
  }, [permissionsGranted]);

  const handleSelectAnswer = useCallback((questionId, optionIndex) => {
    setAnswers(prev => ({ ...prev, [questionId]: optionIndex }));
  }, []);

  // Calculate score (internal, not shown to user)
  const calculateScore = useCallback(() => {
    if (!exam) return { correct: 0, total: 0 };
    let correct = 0;
    exam.questions.forEach(q => {
      if (answers[q.id] === q.correctAnswer) correct++;
    });
    return { correct, total: exam.questions.length };
  }, [exam, answers]);

  const doSubmit = useCallback(() => {
    // Stop media streams
    if (window.__examCameraStream) {
      window.__examCameraStream.getTracks().forEach(t => t.stop());
      window.__examCameraStream = null;
    }
    if (window.__examScreenStream) {
      window.__examScreenStream.getTracks().forEach(t => t.stop());
      window.__examScreenStream = null;
    }

    const score = calculateScore();
    const timeSpent = exam.duration * 60 - timeLeft;

    // Save score to localStorage (for admin review, not shown to student)
    const submission = {
      examId: exam.id,
      examTitle: exam.title,
      totalQuestions: exam.questions.length,
      answeredCount: Object.keys(answers).length,
      correctCount: score.correct,
      scorePercent: Math.round((score.correct / score.total) * 100),
      timeSpent,
      submittedAt: new Date().toISOString(),
      answers: { ...answers }
    };
    localStorage.setItem('exam_submission_' + exam.id, JSON.stringify(submission));

    navigate('/result', {
      state: {
        examTitle: exam.title,
        totalQuestions: exam.questions.length,
        answeredCount: Object.keys(answers).length,
        submittedAt: submission.submittedAt,
        timeSpent
      }
    });
  }, [exam, answers, timeLeft, navigate, calculateScore]);

  const handleAutoSubmit = useCallback(() => {
    doSubmit();
  }, [doSubmit]);

  // Format time
  const formatTime = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const getTimerClass = () => {
    if (timeLeft <= 300) return 'timer danger';
    if (timeLeft <= 600) return 'timer warning';
    return 'timer';
  };

  // Build render list with section headers
  const renderItems = useMemo(() => {
    if (!exam) return [];
    const items = [];
    let lastSection = null;
    let lastPart = null;

    exam.questions.forEach((q, idx) => {
      const sectionDef = exam.sections[q.section];
      
      // Insert part header when part changes
      if (sectionDef && sectionDef.part !== lastPart) {
        items.push({ type: 'part', key: `part-${q.section}`, title: sectionDef.part });
        lastPart = sectionDef.part;
      }
      
      // Insert section header when section changes
      if (q.section !== lastSection) {
        items.push({
          type: 'section',
          key: `section-${q.section}`,
          title: sectionDef?.title || '',
          instruction: sectionDef?.instruction || ''
        });
        lastSection = q.section;
      }

      items.push({ type: 'question', key: `q-${q.id}`, question: q, index: idx });
    });

    return items;
  }, [exam]);

  if (!exam) {
    return (
      <div className="exam-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div className="glass-card" style={{ padding: '48px', textAlign: 'center' }}>
          <h2>Không tìm thấy bài thi</h2>
          <button className="btn-primary" onClick={() => navigate('/exams')} style={{ marginTop: '24px' }}>Quay lại</button>
        </div>
      </div>
    );
  }

  const answeredCount = Object.keys(answers).length;
  const progressPercent = (answeredCount / exam.questions.length) * 100;

  if (!permissionsGranted) {
    return <PermissionModal onPermissionsGranted={() => setPermissionsGranted(true)} />;
  }

  return (
    <div className="exam-page">
      {/* Sticky Header */}
      <header className="exam-header">
        <div className="exam-header-left">
          <span className="exam-name">{exam.title}</span>
          <div className="monitor-indicator" title={wsConnected ? 'Hệ thống giám sát đang hoạt động' : 'Mất kết nối giám sát'}>
            <span className={`monitor-dot ${wsConnected ? 'connected' : 'disconnected'}`} />
            <span className="monitor-label">{wsConnected ? 'Giám sát' : 'Mất kết nối'}</span>
            {violationCount > 0 && (
              <span className="violation-badge">{violationCount}</span>
            )}
          </div>
        </div>
        <div className="exam-header-center">
          <div className={getTimerClass()}>
            <span>⏱️</span>
            <span>{formatTime(timeLeft)}</span>
          </div>
          <div className="progress-info">
            Đã trả lời: <span className="answered">{answeredCount}</span> / {exam.questions.length}
          </div>
        </div>
        <div className="exam-header-right">
          <button className="btn-submit" onClick={() => setShowConfirm(true)} id="submit-exam-btn">
            Nộp bài
          </button>
        </div>
      </header>

      {/* Progress Bar + Questions */}
      <div className="exam-body">
        <div className="progress-bar-container">
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }} />
          </div>
        </div>

        {renderItems.map(item => {
          if (item.type === 'part') {
            return (
              <div key={item.key} className="part-divider">
                <div className="part-divider-line" />
                <h2 className="part-title">{item.title}</h2>
                <div className="part-divider-line" />
              </div>
            );
          }
          if (item.type === 'section') {
            return (
              <div key={item.key} className="section-block">
                <h3 className="section-title">{item.title}</h3>
                <p className="section-instruction">{item.instruction}</p>
              </div>
            );
          }
          return (
            <QuestionCard
              key={item.key}
              question={item.question}
              index={item.index}
              selectedAnswer={answers[item.question.id]}
              onSelectAnswer={handleSelectAnswer}
            />
          );
        })}
      </div>

      {/* Camera Preview */}
      {/* <CameraPreview /> */}

      {/* Confirm Dialog */}
      {showConfirm && (
        <div className="confirm-overlay">
          <div className="confirm-dialog glass-card">
            <h3>Xác nhận nộp bài</h3>
            <p>
              Bạn đã trả lời <strong>{answeredCount}/{exam.questions.length}</strong> câu hỏi.
              {answeredCount < exam.questions.length && (
                <><br />Còn <strong>{exam.questions.length - answeredCount}</strong> câu chưa trả lời.</>
              )}
              <br />Bạn có chắc muốn nộp bài?
            </p>
            <div className="confirm-actions">
              <button className="btn-secondary" onClick={() => setShowConfirm(false)}>Tiếp tục làm bài</button>
              <button className="btn-primary" onClick={doSubmit} id="confirm-submit-btn">Nộp bài</button>
            </div>
          </div>
        </div>
      )}
      {/* Screen Share Loss Overlay */}
      {!screenShareActive && (
        <div className="confirm-overlay" style={{ zIndex: 1000, background: 'rgba(0,0,0,0.85)' }}>
          <div className="confirm-dialog glass-card" style={{ borderLeft: '4px solid var(--color-danger)' }}>
            <h3 style={{ color: 'var(--color-danger)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              ⚠️ CẢNH BÁO
            </h3>
            <p style={{ marginTop: '16px' }}>
              Bạn đã dừng chia sẻ màn hình. Để đảm bảo tính công bằng, hệ thống đã tạm dừng làm bài.
            </p>
            <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
              Vui lòng <strong>chia sẻ lại Toàn màn hình</strong> để tiếp tục, hoặc bài thi sẽ bị thu lại.
            </p>
            <div className="confirm-actions" style={{ marginTop: '24px' }}>
              <button 
                className="btn-primary" 
                onClick={async () => {
                  try {
                    const stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'monitor' } });
                    const track = stream.getVideoTracks()[0];
                    if (track.getSettings().displaySurface !== 'monitor') {
                      track.stop();
                      alert("Vui lòng chọn thẻ 'Toàn màn hình' (Entire screen). Không được chọn Tab hoặc Cửa sổ.");
                      return;
                    }
                    window.__examScreenStream = stream;
                    setScreenShareActive(true);
                  } catch (e) {
                    console.error("Screen share failed", e);
                  }
                }}
              >
                Chia sẻ lại màn hình
              </button>
              <button className="btn-secondary" onClick={doSubmit}>
                Nộp bài ngay
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Camera Loss Overlay */}
      {!cameraActive && screenShareActive && (
        <div className="confirm-overlay" style={{ zIndex: 1000, background: 'rgba(0,0,0,0.85)' }}>
          <div className="confirm-dialog glass-card" style={{ borderLeft: '4px solid var(--color-danger)' }}>
            <h3 style={{ color: 'var(--color-danger)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              ⚠️ CẢNH BÁO
            </h3>
            <p style={{ marginTop: '16px' }}>
              Kết nối Camera của bạn đã bị ngắt. Để đảm bảo tính công bằng, hệ thống đã tạm dừng làm bài.
            </p>
            <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
              Vui lòng <strong>kết nối lại Camera</strong> để tiếp tục, hoặc bài thi sẽ bị thu lại.
            </p>
            <div className="confirm-actions" style={{ marginTop: '24px' }}>
              <button 
                className="btn-primary" 
                onClick={async () => {
                  try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                    window.__examCameraStream = stream;
                    setCameraActive(true);
                  } catch (e) {
                    console.error("Camera connect failed", e);
                    alert("Không thể kết nối Camera. Vui lòng cấp quyền trong trình duyệt.");
                  }
                }}
              >
                Kết nối lại Camera
              </button>
              <button className="btn-secondary" onClick={doSubmit}>
                Nộp bài ngay
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
