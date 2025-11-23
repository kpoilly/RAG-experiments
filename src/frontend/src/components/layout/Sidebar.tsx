import { MessageSquare, Settings, Info, LogOut } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';

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
		<div className="flex flex-col h-full bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors duration-300">
			{/* Header - Fixed Height for Alignment */}
			<div className="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-800 shrink-0">
				<div className="flex items-center gap-3">
					<div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center shadow-lg shadow-primary-500/20 overflow-hidden">
						<img src="/favicon-dark.png" alt="Logo" className="w-full h-full object-cover" />
					</div>
					<span className="font-bold text-lg tracking-tight">RAG Assistant</span>
				</div>
			</div>

			<nav className="flex-1 p-4 space-y-2 overflow-y-auto">
				{navItems.map((item) => {
					const Icon = item.icon;
					const isActive = currentPage === item.id;
					return (
						<button
							key={item.id}
							onClick={() => onNavigate(item.id)}
							className={cn(
								"w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group",
								isActive
									? "bg-primary-50/50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400 font-medium"
									: "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200"
							)}
						>
							<Icon className={cn("w-5 h-5 transition-colors", isActive ? "text-primary-600 dark:text-primary-400" : "text-gray-500 dark:text-gray-500 group-hover:text-gray-700 dark:group-hover:text-gray-300")} />
							{item.label}
						</button>
					);
				})}
			</nav>

			<div className="p-4 border-t border-gray-200 dark:border-gray-800 shrink-0 pb-6">
				<button
					onClick={logout}
					className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-gray-600 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 group"
				>
					<LogOut className="w-5 h-5 group-hover:text-red-600 dark:group-hover:text-red-400 transition-colors" />
					Logout
				</button>
			</div>
		</div>
	);
}
