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
			<div className="flex-1 flex flex-col min-w-0">
				{/* Header - Fixed Height for Alignment */}
				<div className="h-16 flex items-center justify-between px-6 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
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

				{/* Input Area */}
				<div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
					<form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative">
						<input
							ref={inputRef}
							type="text"
							placeholder="Ask a question..."
							className="w-full bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl pl-4 pr-12 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-500/50 transition-all placeholder:text-gray-500 dark:placeholder:text-gray-400"
							disabled={isLoading}
						/>
						<button
							type="submit"
							disabled={isLoading}
							className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 disabled:hover:bg-primary-600 transition-colors shadow-sm"
						>
							{isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
						</button>
					</form>
				</div>
			</div>

			{/* Document Sidebar */}
			<DocumentSidebar />
		</div>
	);
}
