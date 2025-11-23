import { useState, type ReactNode } from 'react';
import { AuthContext } from './AuthContext';

export function AuthProvider({ children }: { children: ReactNode }) {
	const [token, setToken] = useState<string | null>(() => {
		return localStorage.getItem('auth_token');
	});

	const login = (newToken: string) => {
		localStorage.setItem('auth_token', newToken);
		setToken(newToken);
	};

	const logout = () => {
		localStorage.removeItem('auth_token');
		setToken(null);
	};

	return (
		<AuthContext.Provider value={{ token, login, logout, isAuthenticated: !!token }}>
			{children}
		</AuthContext.Provider>
	);
}
