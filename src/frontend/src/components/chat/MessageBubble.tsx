import React from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import { User, Bot } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { Message } from '../../types';
import { CitationTooltip } from './CitationTooltip';

interface MessageBubbleProps {
	message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
	const isUser = message.role === 'user';

	const processText = (text: string) => {
		if (!message.sources || message.sources.length === 0) return text;

		const parts = text.split(/(\[\d+\])/g);
		return parts.map((part, i) => {
			const match = part.match(/^\[(\d+)\]$/);
			if (match) {
				const index = parseInt(match[1]);
				const source = message.sources?.find(s => s.index === index);
				if (source) {
					return <CitationTooltip key={i} source={source} />;
				}
			}
			return part;
		});
	};

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3 }}
			className={cn("flex gap-4 max-w-3xl mx-auto w-full", isUser ? "flex-row-reverse" : "flex-row")}
		>
			<div className={cn(
				"w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
				isUser ? "bg-primary-600" : "bg-accent-400"
			)}>
				{isUser ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
			</div>

			<div className={cn(
				"flex-1 px-6 py-4 max-w-[85%] shadow-sm",
				isUser
					? "bg-primary-600 text-white rounded-t-[2rem] rounded-bl-[2rem] rounded-br-sm"
					: "bg-surface-100 dark:bg-surface-800 text-surface-900 dark:text-surface-100 rounded-t-[2rem] rounded-br-[2rem] rounded-bl-sm"
			)}>
				<ReactMarkdown
					components={{
						p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{
							React.Children.map(children, child =>
								typeof child === 'string' ? processText(child) : child
							)
						}</p>,
						code: ({ className, children, ...props }) => {
							const isInline = !className;
							return isInline
								? <code className="bg-gray-900/50 rounded px-1 py-0.5 text-sm font-mono text-pink-400" {...props}>{children}</code>
								: <code className={cn("block bg-gray-900 p-4 rounded-lg text-sm font-mono overflow-x-auto my-2", className)} {...props}>{children}</code>;
						},
						ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
						ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
						li: ({ children }) => <li className="leading-relaxed">{
							React.Children.map(children, child =>
								typeof child === 'string' ? processText(child) : child
							)
						}</li>,
					}}
				>
					{message.content}
				</ReactMarkdown>
			</div>
		</motion.div>
	);
}
