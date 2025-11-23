import { useState, useEffect } from 'react';
import { useAuth } from './useAuth';

const STORAGE_KEY = 'rag_settings';

interface Settings {
	temperature: number;
	strictMode: boolean;
	rerankThreshold: number;
	llmModel1: string;
	llmModel2: string;
	embeddingModel: string;
	rerankerModel: string;
}

const DEFAULT_SETTINGS: Settings = {
	temperature: 0.2,
	strictMode: false,
	rerankThreshold: 0.0,
	llmModel1: 'llm_model', // Placeholder
	llmModel2: 'llm_side_model', // Placeholder
	embeddingModel: 'embedding_model', // Placeholder
	rerankerModel: 'reranker_model', // Placeholder
};

export function useSettings() {
	const [settings, setSettings] = useState<Settings>(() => {
		const saved = localStorage.getItem('rag_settings');
		return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
	});

	useEffect(() => {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
	}, [settings]);

	const { token } = useAuth();

	useEffect(() => {
		const fetchConfig = async () => {
			if (!token) return;
			try {
				const response = await fetch('/api/config', {
					headers: {
						'Authorization': `Bearer ${token}`
					}
				});
				if (response.ok) {
					const data = await response.json();
					setSettings(prev => ({
						...prev,
						llmModel1: data.llm_model,
						llmModel2: data.llm_side_model,
						embeddingModel: data.embedding_model,
						rerankerModel: data.reranker_model,
					}));
				}
			} catch (error) {
				console.error('Failed to fetch RAG config:', error);
			}
		};

		fetchConfig();
	}, [token]);

	const updateSettings = (newSettings: Partial<Settings>) => {
		setSettings((prev) => {
			const updated = { ...prev, ...newSettings };
			localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
			return updated;
		});
	};

	return { settings, updateSettings };
}
