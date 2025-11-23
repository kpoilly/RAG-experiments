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
		<div className="flex h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 overflow-hidden font-sans antialiased selection:bg-blue-500/30 transition-colors duration-300">
			{/* Mobile Menu Button */}
			<button
				className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-gray-800 rounded-lg text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shadow-lg border border-gray-200 dark:border-gray-700"
				onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
			>
				{isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
			</button>

			{/* Theme Toggle - Absolute Position */}
			<button
				onClick={toggleTheme}
				className="fixed top-4 right-4 z-50 p-2 bg-white dark:bg-gray-800 rounded-lg text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shadow-lg border border-gray-200 dark:border-gray-700"
				title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
			>
				{theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
			</button>

			{/* Sidebar - Desktop */}
			<div className="hidden lg:block h-full shadow-xl z-10 relative border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
				<Sidebar currentPage={currentPage} onNavigate={handleNavigate} />
			</div>

			{/* Sidebar - Mobile */}
			{isMobileMenuOpen && (
				<div className="lg:hidden fixed inset-0 z-40 bg-gray-900/50 backdrop-blur-sm transition-opacity">
					<div className="w-64 h-full shadow-2xl bg-white dark:bg-gray-900">
						<Sidebar currentPage={currentPage} onNavigate={handleNavigate} />
					</div>
					<div className="absolute inset-0 -z-10" onClick={() => setIsMobileMenuOpen(false)} />
				</div>
			)}

			<main className="flex-1 flex flex-col min-w-0 overflow-hidden relative w-full lg:pl-0 pl-0 pt-0 bg-gray-50 dark:bg-gray-900">
				<Outlet />
			</main>
		</div>
	);
}
