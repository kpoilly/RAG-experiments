import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../hooks/useAuth';
import { Lock, Mail, UserPlus, LogIn, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

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
		<div className="min-h-screen bg-surface-50 dark:bg-surface-950 flex items-center justify-center p-4 transition-colors duration-300 overflow-hidden relative">
			{/* Background Blobs */}
			<div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-400/20 rounded-full blur-[100px] animate-pulse" />
			<div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-accent-400/20 rounded-full blur-[100px] animate-pulse delay-1000" />

			<motion.div
				initial={{ opacity: 0, y: 20, scale: 0.95 }}
				animate={{ opacity: 1, y: 0, scale: 1 }}
				transition={{ duration: 0.5, type: "spring" }}
				className="w-full max-w-md relative z-10"
			>
				{/* Logo & Title */}
				<div className="text-center mb-8">
					<motion.div
						whileHover={{ rotate: 10, scale: 1.05 }}
						className="inline-flex items-center justify-center w-20 h-20 bg-primary-500 rounded-[2rem] shadow-2xl shadow-primary-500/30 mb-6 overflow-hidden rotate-3 hover:rotate-0 transition-all duration-300"
					>
						<img src="/favicon-dark.png" alt="Logo" className="w-full h-full object-cover scale-110" />
					</motion.div>
					<h1 className="text-4xl font-bold text-surface-900 dark:text-surface-50 mb-3 tracking-tight">
						RAG Assistant
					</h1>
					<p className="text-lg text-surface-600 dark:text-surface-400">
						{isLogin ? 'Welcome back!' : 'Create your account'}
					</p>
				</div>

				{/* Card */}
				<div className="bg-white/80 dark:bg-surface-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl shadow-surface-200/50 dark:shadow-black/50 border border-white/50 dark:border-surface-700/50 overflow-hidden">
					<div className="p-8">
						{/* Tabs */}
						<div className="flex mb-8 bg-surface-100 dark:bg-surface-800/50 rounded-[1.25rem] p-1.5 relative">
							<div className="absolute inset-1.5 flex pointer-events-none">
								<motion.div
									layoutId="activeTabLogin"
									className="w-1/2 h-full bg-white dark:bg-surface-700 rounded-2xl shadow-sm"
									animate={{ x: isLogin ? '0%' : '100%' }}
									transition={{ type: "spring", stiffness: 300, damping: 30 }}
								/>
							</div>
							<button
								onClick={() => setIsLogin(true)}
								className={`flex-1 py-3 text-sm font-bold rounded-2xl transition-colors relative z-10 ${isLogin
									? 'text-surface-900 dark:text-surface-50'
									: 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-200'
									}`}
							>
								Login
							</button>
							<button
								onClick={() => setIsLogin(false)}
								className={`flex-1 py-3 text-sm font-bold rounded-2xl transition-colors relative z-10 ${!isLogin
									? 'text-surface-900 dark:text-surface-50'
									: 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-200'
									}`}
							>
								Register
							</button>
						</div>

						<form onSubmit={handleSubmit} className="space-y-6">
							<AnimatePresence mode="wait">
								{error && (
									<motion.div
										initial={{ opacity: 0, height: 0 }}
										animate={{ opacity: 1, height: 'auto' }}
										exit={{ opacity: 0, height: 0 }}
										className={`p-4 rounded-2xl text-sm font-medium ${error.includes('successful')
											? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20'
											: 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border border-red-100 dark:border-red-500/20'
											}`}
									>
										{error}
									</motion.div>
								)}
							</AnimatePresence>

							<div className="space-y-2">
								<label className="text-sm font-bold text-surface-700 dark:text-surface-300 ml-1">Email</label>
								<div className="relative group">
									<Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400 dark:text-surface-500 group-focus-within:text-primary-500 transition-colors" />
									<input
										type="email"
										value={email}
										onChange={(e) => setEmail(e.target.value)}
										className="w-full bg-surface-50 dark:bg-surface-950/50 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-50 rounded-2xl pl-12 pr-4 py-4 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all placeholder:text-surface-400 dark:placeholder:text-surface-600"
										placeholder="name@example.com"
										required
									/>
								</div>
							</div>

							<div className="space-y-2">
								<label className="text-sm font-bold text-surface-700 dark:text-surface-300 ml-1">Password</label>
								<div className="relative group">
									<Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400 dark:text-surface-500 group-focus-within:text-primary-500 transition-colors" />
									<input
										type="password"
										value={password}
										onChange={(e) => setPassword(e.target.value)}
										className="w-full bg-surface-50 dark:bg-surface-950/50 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-50 rounded-2xl pl-12 pr-4 py-4 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all placeholder:text-surface-400 dark:placeholder:text-surface-600"
										placeholder="••••••••"
										required
									/>
								</div>
							</div>

							<motion.button
								whileHover={{ scale: 1.02 }}
								whileTap={{ scale: 0.98 }}
								type="submit"
								disabled={isLoading}
								className="w-full bg-primary-600 hover:bg-primary-500 text-white font-bold py-4 rounded-2xl transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-primary-500/30 hover:shadow-primary-500/50"
							>
								{isLoading ? (
									<Loader2 className="w-6 h-6 animate-spin" />
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
							</motion.button>
						</form>
					</div>
				</div>
			</motion.div>
		</div>
	);
}
