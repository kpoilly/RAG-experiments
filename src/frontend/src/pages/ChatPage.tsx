import { useRef, useEffect } from 'react';
import { Send, Loader2, Trash2 } from 'lucide-react';
import { useChat } from '../hooks/useChat';
import { MessageBubble } from '../components/chat/MessageBubble';
import { ThinkingBubble } from '../components/chat/ThinkingBubble';
import { DocumentSidebar } from '../components/documents/DocumentSidebar';

export function ChatPage() {
	const { messages, sendMessage, isLoading, clearHistory } = useChat();
	const messagesEndRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLInputElement>(null);

	const scrollToBottom = () => {
		messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
	};

	useEffect(() => {
		scrollToBottom();
	}, [messages]);

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (inputRef.current?.value.trim()) {
			sendMessage(inputRef.current.value);
			inputRef.current.value = '';
		}
	};

	return (
		<div className="flex h-full bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
			{/* Main Chat Area */}
			<div className="flex-1 flex flex-col min-w-0 bg-surface-50 dark:bg-surface-950">
				{/* Header - Transparent/Glass */}
				<div className="h-20 flex items-center justify-between px-8 shrink-0">
					<h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">Chat</h2>
					<button
						onClick={clearHistory}
						className="p-2 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 transition-colors rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
						title="Clear History"
					>
						<Trash2 className="w-5 h-5" />
					</button>
				</div>

				{/* Messages Area */}
				<div className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth">
					{messages.length === 0 ? (
						<div className="h-full flex flex-col items-center justify-center text-gray-400 dark:text-gray-500 space-y-4">
							<div className="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-2xl flex items-center justify-center">
								<Send className="w-8 h-8 text-gray-300 dark:text-gray-600" />
							</div>
							<p className="text-lg font-medium">Start a conversation with your documents</p>
						</div>
					) : (
						<>
							{messages.map((msg, idx) => (
								<MessageBubble key={idx} message={msg} />
							))}
							{isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
								<div className="py-4">
									<ThinkingBubble />
								</div>
							)}
							<div ref={messagesEndRef} />
						</>
					)}
				</div>

				{/* Input Area - Floating Pill */}
				<div className="p-6 bg-transparent shrink-0">
					<form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative">
						<div className="relative group">
							<div className="absolute -inset-0.5 bg-gradient-to-r from-primary-500 to-accent-500 rounded-full opacity-20 group-hover:opacity-40 transition duration-500 blur"></div>
							<div className="relative flex items-center bg-surface-50 dark:bg-surface-900 rounded-full shadow-xl border border-surface-200 dark:border-surface-700 p-2 transition-transform duration-300 focus-within:scale-[1.01]">
								<input
									ref={inputRef}
									type="text"
									placeholder="Ask anything..."
									className="flex-1 bg-transparent text-surface-900 dark:text-surface-100 placeholder:text-surface-400 dark:placeholder:text-surface-500 px-6 py-3 focus:outline-none text-lg"
									disabled={isLoading}
								/>
								<button
									type="submit"
									disabled={isLoading}
									className="p-3 bg-primary-600 text-white rounded-full hover:bg-primary-500 disabled:opacity-50 disabled:hover:bg-primary-600 transition-all duration-300 hover:rotate-90 hover:scale-110 shadow-lg shadow-primary-500/30"
								>
									{isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
								</button>
							</div>
						</div>
					</form>
				</div>
			</div>

			{/* Document Sidebar */}
			<DocumentSidebar />
		</div>
	);
}
