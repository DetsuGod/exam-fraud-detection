import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check localStorage for existing session
    const savedUser = localStorage.getItem('exam_user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('exam_user');
      }
    }
    setLoading(false);
  }, []);

  const login = (studentId, password) => {
    // Mock authentication - accept any non-empty credentials
    if (!studentId.trim() || !password.trim()) {
      return { success: false, error: 'Vui lòng nhập đầy đủ thông tin.' };
    }

    const userData = {
      studentId: studentId.trim(),
      name: `Thí sinh ${studentId.trim()}`,
      loginTime: new Date().toISOString()
    };

    localStorage.setItem('exam_user', JSON.stringify(userData));
    setUser(userData);
    return { success: true };
  };

  const logout = () => {
    localStorage.removeItem('exam_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
