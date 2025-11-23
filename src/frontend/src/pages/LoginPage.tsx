import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../hooks/useAuth';
import { Lock, Mail, UserPlus, LogIn, Loader2 } from 'lucide-react';

export function LoginPage() {
	const [isLogin, setIsLogin] = useState(true);
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState('');
	const { login } = useAuth();
	const navigate = useNavigate();

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setIsLoading(true);
		setError('');

		try {
			if (isLogin) {
				const formData = new FormData();
				formData.append('username', email);
				formData.append('password', password);

				const response = await axios.post('/api/auth/token', formData);
				login(response.data.access_token);
				navigate('/');
			} else {
				await axios.post('/api/auth/register', { email, password });
				setIsLogin(true);
				setError('Registration successful! Please login.');
				setTimeout(() => setError(''), 3000);
			}
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
		} catch (err: any) {
			setError(err.response?.data?.detail || 'An error occurred');
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4 transition-colors duration-300">
			<div className="w-full max-w-md">
				{/* Logo & Title */}
				<div className="text-center mb-8">
					<div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-2xl shadow-lg shadow-primary-500/20 mb-4 overflow-hidden">
						<img src="/favicon-dark.png" alt="Logo" className="w-full h-full object-cover" />
					</div>
					<h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
						RAG Assistant
					</h1>
					<p className="text-gray-600 dark:text-gray-400">
						{isLogin ? 'Welcome back!' : 'Create your account'}
					</p>
				</div>

				{/* Card */}
				<div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden transition-colors duration-300">
					<div className="p-8">
						{/* Tabs */}
						<div className="flex mb-6 bg-gray-100 dark:bg-gray-900/50 rounded-xl p-1">
							<button
								onClick={() => setIsLogin(true)}
								className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${isLogin
									? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
									: 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
									}`}
							>
								Login
							</button>
							<button
								onClick={() => setIsLogin(false)}
								className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${!isLogin
									? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
									: 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
									}`}
							>
								Register
							</button>
						</div>

						<form onSubmit={handleSubmit} className="space-y-5">
							{error && (
								<div className={`p-3 rounded-xl text-sm ${error.includes('successful')
									? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20'
									: 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-500/20'
									}`}>
									{error}
								</div>
							)}

							<div className="space-y-2">
								<label className="text-sm font-medium text-gray-700 dark:text-gray-300">Email</label>
								<div className="relative">
									<Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 dark:text-gray-500" />
									<input
										type="email"
										value={email}
										onChange={(e) => setEmail(e.target.value)}
										className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white rounded-xl pl-10 pr-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500"
										placeholder="name@example.com"
										required
									/>
								</div>
							</div>

							<div className="space-y-2">
								<label className="text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
								<div className="relative">
									<Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 dark:text-gray-500" />
									<input
										type="password"
										value={password}
										onChange={(e) => setPassword(e.target.value)}
										className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white rounded-xl pl-10 pr-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500"
										placeholder="••••••••"
										required
									/>
								</div>
							</div>

							<button
								type="submit"
								disabled={isLoading}
								className="w-full bg-primary-600 hover:bg-primary-500 text-white font-medium py-3 rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md"
							>
								{isLoading ? (
									<Loader2 className="w-5 h-5 animate-spin" />
								) : isLogin ? (
									<>
										<LogIn className="w-5 h-5" />
										Sign In
									</>
								) : (
									<>
										<UserPlus className="w-5 h-5" />
										Create Account
									</>
								)}
							</button>
						</form>
					</div>
				</div>
			</div>
		</div>
	);
}
