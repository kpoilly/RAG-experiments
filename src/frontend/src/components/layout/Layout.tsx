import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Menu, X, Sun, Moon } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { useTheme } from '../../context/ThemeContext';

export function Layout() {
	const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
	const { theme, toggleTheme } = useTheme();
	const navigate = useNavigate();
	const location = useLocation();
	const currentPage = location.pathname.split('/')[1] || 'chat';

	const handleNavigate = (page: string) => {
		navigate(`/${page}`);
		setIsMobileMenuOpen(false);
	};

	return (
		<div className="flex h-screen bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-50 overflow-hidden font-sans antialiased selection:bg-primary-200 selection:text-primary-900 transition-colors duration-300">
			{/* Mobile Menu Button */}
			<button
				className="lg:hidden fixed top-4 left-4 z-50 p-3 bg-surface-50/80 dark:bg-surface-900/80 backdrop-blur-md rounded-2xl text-surface-600 dark:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors shadow-lg border border-surface-200 dark:border-surface-700"
				onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
			>
				{isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
			</button>

			{/* Theme Toggle - Absolute Position */}
			<button
				onClick={toggleTheme}
				className="fixed top-4 right-4 z-50 p-3 bg-surface-50/80 dark:bg-surface-900/80 backdrop-blur-md rounded-2xl text-surface-600 dark:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors shadow-lg border border-surface-200 dark:border-surface-700 group"
				title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
			>
				{theme === 'dark' ? (
					<Sun className="w-5 h-5 group-hover:text-amber-500 transition-colors" />
				) : (
					<Moon className="w-5 h-5 group-hover:text-primary-500 transition-colors" />
				)}
			</button>

			{/* Sidebar - Desktop */}
			<div className="hidden lg:block h-full w-80 z-10 relative">
				<Sidebar currentPage={currentPage} onNavigate={handleNavigate} />
			</div>

			{/* Sidebar - Mobile */}
			{isMobileMenuOpen && (
				<div className="lg:hidden fixed inset-0 z-40 bg-surface-900/50 backdrop-blur-sm transition-opacity">
					<div className="w-80 h-full">
						<Sidebar currentPage={currentPage} onNavigate={handleNavigate} />
					</div>
					<div className="absolute inset-0 -z-10" onClick={() => setIsMobileMenuOpen(false)} />
				</div>
			)}

			<main className="flex-1 flex flex-col min-w-0 overflow-hidden relative w-full lg:pl-0 pl-0 pt-0">
				<Outlet />
			</main>
		</div>
	);
}
