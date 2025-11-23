import { MessageSquare, Settings, Info, LogOut } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';
import { motion } from 'framer-motion';

interface SidebarProps {
	currentPage: string;
	onNavigate: (page: string) => void;
}

export function Sidebar({ currentPage, onNavigate }: SidebarProps) {
	const { logout } = useAuth();

	const navItems = [
		{ id: 'chat', label: 'Chat', icon: MessageSquare },
		{ id: 'settings', label: 'Settings', icon: Settings },
		{ id: 'info', label: 'Info', icon: Info },
	];

	return (
		<div className="h-full flex flex-col p-4">
			{/* Floating Island Container */}
			<div className="flex-1 flex flex-col bg-surface-50/80 dark:bg-surface-900/80 backdrop-blur-xl border border-surface-200/50 dark:border-surface-700/50 rounded-[2rem] shadow-2xl shadow-surface-200/50 dark:shadow-black/20 overflow-hidden">

				{/* Header */}
				<div className="h-20 flex items-center px-6 shrink-0">
					<div className="flex items-center gap-4">
						<div className="w-10 h-10 bg-primary-500 rounded-2xl flex items-center justify-center shadow-lg shadow-primary-500/20 overflow-hidden rotate-3 hover:rotate-0 transition-transform duration-300">
							<img src="/favicon-dark.png" alt="Logo" className="w-full h-full object-cover scale-110" />
						</div>
						<span className="font-bold text-xl tracking-tight text-surface-900 dark:text-surface-50">RAG Assistant</span>
					</div>
				</div>

				{/* Navigation */}
				<nav className="flex-1 px-4 space-y-2 overflow-y-auto py-4">
					{navItems.map((item) => {
						const Icon = item.icon;
						const isActive = currentPage === item.id;
						return (
							<button
								key={item.id}
								onClick={() => onNavigate(item.id)}
								className={cn(
									"relative w-full flex items-center gap-4 px-5 py-4 rounded-2xl transition-all duration-300 group overflow-hidden",
									isActive
										? "text-primary-700 dark:text-primary-100 font-semibold"
										: "text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200"
								)}
							>
								{isActive && (
									<motion.div
										layoutId="activeTab"
										className="absolute inset-0 bg-primary-100 dark:bg-primary-500/20 rounded-2xl"
										initial={false}
										transition={{ type: "spring", stiffness: 300, damping: 30 }}
									/>
								)}
								<div className="relative z-10 flex items-center gap-4">
									<Icon className={cn(
										"w-5 h-5 transition-colors duration-300",
										isActive ? "text-primary-600 dark:text-primary-300" : "text-surface-400 dark:text-surface-500 group-hover:text-surface-600 dark:group-hover:text-surface-300"
									)} />
									<span>{item.label}</span>
								</div>
							</button>
						);
					})}
				</nav>

				{/* Footer */}
				<div className="p-4 shrink-0">
					<button
						onClick={logout}
						className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl text-surface-600 dark:text-surface-400 hover:bg-red-50 dark:hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 group"
					>
						<LogOut className="w-5 h-5 group-hover:text-red-600 dark:group-hover:text-red-400 transition-colors" />
						<span className="font-medium">Logout</span>
					</button>
				</div>
			</div>
		</div>
	);
}
