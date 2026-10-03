import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import api, {
  AUTH_SESSION_CLEARED_EVENT,
  clearAuthTokens,
  getStoredAuth,
  login as apiLogin,
  logout as apiLogout,
  setAuthTokens,
  startAuthKeepAlive,
} from '../services/api';

const AuthContext = createContext(null);
const USER_CACHE_KEY = 'hr_user_cache';
const SESSION_CHECK_TIMEOUT_MS = 15000;

function readCachedUser() {
  try {
    const raw = sessionStorage.getItem(USER_CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCachedUser(user) {
  if (!user) {
    sessionStorage.removeItem(USER_CACHE_KEY);
    return;
  }
  sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
}

export function AuthProvider({ children }) {
  // Do not treat a cached user as signed-in until /auth/me succeeds.
  // Painting the dashboard with a stale token is what left a blank screen.
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(getStoredAuth()?.accessToken));
  const loadGenRef = useRef(0);

  const loadUser = useCallback(async ({ blockUi = true } = {}) => {
    const stored = getStoredAuth();
    if (!stored?.accessToken) {
      setUser(null);
      writeCachedUser(null);
      setLoading(false);
      return;
    }

    const gen = ++loadGenRef.current;
    if (blockUi) setLoading(true);

    try {
      const { data } = await api.get('/auth/me', { timeout: SESSION_CHECK_TIMEOUT_MS });
      if (gen !== loadGenRef.current) return;
      setUser(data);
      writeCachedUser(data);
    } catch {
      if (gen !== loadGenRef.current) return;
      if (!getStoredAuth()?.accessToken) {
        setUser(null);
        writeCachedUser(null);
      } else {
        const cached = readCachedUser();
        if (cached) {
          setUser(cached);
        } else {
          setUser(null);
        }
      }
    } finally {
      if (gen === loadGenRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser({ blockUi: true });
  }, [loadUser]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      if (!getStoredAuth()?.accessToken) return;
      void loadUser({ blockUi: false });
    };
    const onSessionCleared = () => {
      loadGenRef.current += 1;
      setUser(null);
      writeCachedUser(null);
      setLoading(false);
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, onSessionCleared);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, onSessionCleared);
    };
  }, [loadUser]);

  useEffect(() => {
    if (!user) return undefined;
    const timer = startAuthKeepAlive();
    return () => window.clearInterval(timer);
  }, [user]);

  const login = async (email, password) => {
    const { data } = await apiLogin(email, password);
    setAuthTokens(data.access_token, data.refresh_token);
    setUser(data.user);
    writeCachedUser(data.user);
    setLoading(false);
    return data.user;
  };

  const logout = async () => {
    const stored = getStoredAuth();
    if (stored?.refreshToken) {
      try {
        await apiLogout(stored.refreshToken);
      } catch {
        /* ignore */
      }
    }
    clearAuthTokens();
    setUser(null);
    writeCachedUser(null);
    setLoading(false);
  };

  const updateCurrentUser = useCallback((nextUser) => {
    setUser(nextUser);
    writeCachedUser(nextUser);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      updateCurrentUser,
      isAuthenticated: Boolean(user),
    }),
    [user, loading, login, logout, updateCurrentUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
