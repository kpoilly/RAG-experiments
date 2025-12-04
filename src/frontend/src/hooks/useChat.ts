import { useState, useCallback, useEffect } from 'react';
import type { Message, Source } from '../types';
import { useAuth } from './useAuth';
import { useSettings } from './useSettings';

export function useChat() {
	const [messages, setMessages] = useState<Message[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const { token, logout } = useAuth();
	const { settings } = useSettings();

	const fetchHistory = useCallback(async () => {
		if (!token) return;
		try {
			const response = await fetch('/api/history', {
				headers: {
					'Authorization': `Bearer ${token}`
				}
			});
			if (response.status === 401) {
				logout();
				return;
			}
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
			const response = await fetch('/api/history', {
				method: 'DELETE',
				headers: {
					'Authorization': `Bearer ${token}`
				}
			});
			if (response.status === 401) {
				logout();
				return;
			}
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
					temperature: settings.temperature,
					strict_rag: settings.strictMode,
					rerank_threshold: settings.rerankThreshold
				}),
			});

			if (response.status === 401) {
				logout();
				setIsLoading(false);
				return;
			}

			if (!response.ok) {
				// Try to read error message from response
				const errorData = await response.json().catch(() => ({}));
				const errorMessage = errorData.content || 'Network response was not ok';

				setMessages(prev => {
					// Remove the user message we optimistically added? Or just add an error message?
					// Let's add an error message from assistant
					const assistantMessage: Message = {
						role: 'assistant',
						content: `Error: ${errorMessage}`
					};
					return [...prev, assistantMessage];
				});
				throw new Error(errorMessage);
			}

			const reader = response.body?.getReader();
			const decoder = new TextDecoder();
			let fullContent = '';
			let sources: Source[] = [];
			let isFirstChunk = true;
			let buffer = '';

			const processLine = (line: string) => {
				if (line.startsWith('data: ')) {
					const dataStr = line.slice(6).trim();
					if (dataStr === '[DONE]') return;

					try {
						const data = JSON.parse(dataStr);

						// Handle error messages from backend
						if (data.type === 'error') {
							const errorMessage = data.content || 'An error occurred';
							setMessages(prev => {
								const newMessages = [...prev];
								const lastMsg = newMessages[newMessages.length - 1];
								if (lastMsg.role === 'assistant') {
									lastMsg.content = `Error: ${errorMessage}`;
								}
								return newMessages;
							});
							// Stop processing further
							return;
						}

						if (data.type === 'sources') {
							sources = data.data;
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
								const assistantMessage: Message = {
									role: 'assistant',
									content: fullContent,
									sources: sources
								};
								setMessages(prev => [...prev, assistantMessage]);
								isFirstChunk = false;
							} else {
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
				} else {
					// Try to parse as raw JSON error (e.g. rate limits or other backend errors)
					try {
						const data = JSON.parse(line);
						let errorMessage: string | null = null;

						if (data.error) {
							errorMessage = data.error.message || JSON.stringify(data.error);
						} else if (data.type === 'error') {
							errorMessage = data.content || 'An error occurred';
						}

						if (errorMessage) {
							// Format error message to be more user-friendly
							if (errorMessage.includes('Rate limit reached')) {
								const waitTimeMatch = errorMessage.match(/Please try again in (\d+\.?\d*s)/);
								const waitTime = waitTimeMatch ? waitTimeMatch[1] : 'a few seconds';
								errorMessage = `Rate limit reached. Please try again in ${waitTime}.`;
							}

							setMessages(prev => {
								// If we haven't started an assistant message yet, add one
								if (isFirstChunk) {
									return [...prev, {
										role: 'assistant',
										content: `Error: ${errorMessage}`
									}];
								}
								// Otherwise update the existing one
								const newMessages = [...prev];
								const lastMsg = newMessages[newMessages.length - 1];
								if (lastMsg.role === 'assistant') {
									lastMsg.content = `Error: ${errorMessage}`;
								}
								return newMessages;
							});
							return;
						}
					} catch (e) {
						// Not a JSON object, ignore
					}
				}
			};

			if (reader) {
				while (true) {
					const { done, value } = await reader.read();

					if (done) {
						// Process any remaining buffer
						if (buffer.trim()) {
							const lines = buffer.split('\n');
							for (const line of lines) {
								processLine(line);
							}
						}
						break;
					}

					buffer += decoder.decode(value, { stream: true });

					// Process complete messages in buffer
					// SSE messages are separated by double newline
					const parts = buffer.split('\n\n');

					// Keep the last part in buffer as it might be incomplete
					// unless the buffer ends with \n\n, in which case the last part is empty
					buffer = parts.pop() || '';

					for (const part of parts) {
						const lines = part.split('\n');
						for (const line of lines) {
							processLine(line);
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
					lastMsg.content = `Sorry, I encountered an error. Please try again.\n\nDetails: ${error instanceof Error ? error.message : String(error)}`;
				}
				return newMessages;
			});
		} finally {
			setIsLoading(false);
		}
	}, [token]);

	return { messages, sendMessage, clearHistory, isLoading };
}
