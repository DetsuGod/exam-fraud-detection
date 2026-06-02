import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PermissionModal from '../components/PermissionModal';

// Sakura petal component
function SakuraBg() {
  const petals = Array.from({ length: 15 }, (_, i) => ({
    id: i,
    left: Math.random() * 100,
    delay: Math.random() * 12,
    duration: 8 + Math.random() * 8,
    size: 8 + Math.random() * 10
  }));

  return (
    <div className="sakura-bg">
      {petals.map(p => (
        <div
          key={p.id}
          className="sakura-petal"
          style={{
            left: `${p.left}%`,
            width: `${p.size}px`,
            height: `${p.size}px`,
            animationDelay: `${p.delay}s`,
            animationDuration: `${p.duration}s`
          }}
        />
      ))}
    </div>
  );
}

export default function LoginPage() {
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [showPermissions, setShowPermissions] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    const result = login(studentId, password);
    if (result.success) {
      setShowPermissions(true);
    } else {
      setError(result.error);
    }
  };

  const handlePermissionsGranted = () => {
    setShowPermissions(false);
    navigate('/exams');
  };

  return (
    <div className="login-page">
      <SakuraBg />

      <div className="login-container glass-card">
        <div className="login-logo">
          <div className="logo-kanji">日本語試験</div>
          <div className="logo-subtitle">Japanese Language Examination</div>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="studentId">Mã số thí sinh</label>
            <input
              id="studentId"
              type="text"
              className="form-input"
              placeholder="Nhập mã số thí sinh..."
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              autoComplete="off"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Mật khẩu</label>
            <input
              id="password"
              type="password"
              className="form-input"
              placeholder="Nhập mật khẩu..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="btn-primary" id="login-btn">
            Đăng nhập
          </button>
        </form>
      </div>

      {showPermissions && (
        <PermissionModal onPermissionsGranted={handlePermissionsGranted} />
      )}
    </div>
  );
}
