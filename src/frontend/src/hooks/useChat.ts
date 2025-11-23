import { useState, useCallback, useEffect } from 'react';
import type { Message, Source } from '../types';
import { useAuth } from './useAuth';

export function useChat() {
	const [messages, setMessages] = useState<Message[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const { token } = useAuth();

	const fetchHistory = useCallback(async () => {
		if (!token) return;
		try {
			const response = await fetch('/api/history', {
				headers: {
					'Authorization': `Bearer ${token}`
				}
			});
			if (response.ok) {
				const data = await response.json();
				setMessages(data);
			}
		} catch (error) {
			console.error('Failed to fetch history:', error);
		}
	}, [token]);

	useEffect(() => {
		fetchHistory();
	}, [fetchHistory]);

	const clearHistory = useCallback(async () => {
		if (!token) return;
		try {
			await fetch('/api/history', {
				method: 'DELETE',
				headers: {
					'Authorization': `Bearer ${token}`
				}
			});
			setMessages([]);
		} catch (error) {
			console.error('Failed to clear history:', error);
		}
	}, [token]);

	const sendMessage = useCallback(async (content: string) => {
		const userMessage: Message = { role: 'user', content };
		setMessages(prev => [...prev, userMessage]);
		setIsLoading(true);

		try {
			const response = await fetch('/api/chat', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${token}`
				},
				body: JSON.stringify({
					query: content,
					temperature: 0.3, // TODO: Get from settings
					strict_rag: false, // TODO: Get from settings
					rerank_threshold: 0.0 // TODO: Get from settings
				}),
			});

			if (!response.ok) throw new Error('Network response was not ok');

			const reader = response.body?.getReader();
			const decoder = new TextDecoder();
			let fullContent = '';
			let sources: Source[] = [];
			let isFirstChunk = true;

			if (reader) {
				while (true) {
					const { done, value } = await reader.read();
					if (done) {
						// Flush any remaining bytes
						const chunk = decoder.decode();
						if (chunk) {
							const lines = chunk.split('\n');
							for (const line of lines) {
								if (line.startsWith('data: ')) {
									const dataStr = line.slice(6).trim();
									if (dataStr === '[DONE]') continue;
									try {
										const data = JSON.parse(dataStr);
										if (data.choices?.[0]?.delta?.content) {
											fullContent += data.choices[0].delta.content;
										}
									} catch (e) {
										console.error('Error parsing final SSE data:', e);
									}
								}
							}
						}
						break;
					}

					const chunk = decoder.decode(value, { stream: true });
					const lines = chunk.split('\n');

					for (const line of lines) {
						if (line.startsWith('data: ')) {
							const dataStr = line.slice(6).trim();
							if (dataStr === '[DONE]') continue;

							try {
								const data = JSON.parse(dataStr);
								if (data.type === 'sources') {
									sources = data.data;
									// Update sources immediately if message exists
									if (!isFirstChunk) {
										setMessages(prev => {
											const newMessages = [...prev];
											const lastMsg = newMessages[newMessages.length - 1];
											if (lastMsg.role === 'assistant') {
												lastMsg.sources = sources;
											}
											return newMessages;
										});
									}
								} else if (data.choices?.[0]?.delta?.content) {
									const content = data.choices[0].delta.content;
									fullContent += content;

									if (isFirstChunk) {
										// Create the assistant message with the first chunk of content
										const assistantMessage: Message = {
											role: 'assistant',
											content: fullContent,
											sources: sources
										};
										setMessages(prev => [...prev, assistantMessage]);
										isFirstChunk = false;
									} else {
										// Update existing message
										setMessages(prev => {
											const newMessages = [...prev];
											const lastMsg = newMessages[newMessages.length - 1];
											if (lastMsg.role === 'assistant') {
												lastMsg.content = fullContent;
											}
											return newMessages;
										});
									}
								}
							} catch (e) {
								console.error('Error parsing SSE data:', e);
							}
						}
					}
				}

				// Final update to ensure consistency
				if (!isFirstChunk) {
					setMessages(prev => {
						const newMessages = [...prev];
						const lastMsg = newMessages[newMessages.length - 1];
						if (lastMsg.role === 'assistant') {
							lastMsg.content = fullContent;
							lastMsg.sources = sources;
						}
						return newMessages;
					});
				}
			}
		} catch (error) {
			console.error('Error sending message:', error);
			setMessages(prev => {
				const newMessages = [...prev];
				const lastMsg = newMessages[newMessages.length - 1];
				if (lastMsg.role === 'assistant') {
					lastMsg.content = 'Sorry, I encountered an error. Please try again.';
				}
				return newMessages;
			});
		} finally {
			setIsLoading(false);
		}
	}, [token]);

	return { messages, sendMessage, clearHistory, isLoading };
}
