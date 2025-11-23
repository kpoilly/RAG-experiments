import { Bot } from 'lucide-react';

export function ThinkingBubble() {
	return (
		<div className="flex gap-4 max-w-3xl mx-auto w-full flex-row animate-in fade-in duration-300">
			<div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-accent-400">
				<Bot className="w-5 h-5 text-white" />
			</div>

			<div className="flex-1 px-6 py-4 max-w-[85%] bg-surface-100 dark:bg-surface-800 rounded-t-[2rem] rounded-br-[2rem] rounded-bl-sm shadow-sm">
				<div className="flex items-center gap-1 h-6">
					<div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
					<div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
					<div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce"></div>
				</div>
			</div>
		</div>
	);
}
