import { useState, useEffect } from 'react';
import { useAuth } from './useAuth';
import axios from 'axios';

const STORAGE_KEY = 'rag_settings';

interface ModelInfo {
	model_name: string;
	model_id: string;
}

interface Settings {
	temperature: number;
	strictMode: boolean;
	rerankThreshold: number;
	llmModel1: string;
	llmModel2: string;
	embeddingModel: string;
	rerankerModel: string;
	apiKey: string;
	sideApiKey: string;
	useMainAsSide: boolean;
}

const DEFAULT_SETTINGS: Settings = {
	temperature: 0.2,
	strictMode: false,
	rerankThreshold: 0.0,
	llmModel1: '',
	llmModel2: '',
	embeddingModel: '',
	rerankerModel: '',
	apiKey: '',
	sideApiKey: '',
	useMainAsSide: false,
};

export function useSettings() {
	const [settings, setSettings] = useState<Settings>(() => {
		const saved = localStorage.getItem(STORAGE_KEY);
		return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
	});
	const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
	const { token, logout } = useAuth();

	useEffect(() => {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
	}, [settings]);

	useEffect(() => {
		const fetchData = async () => {
			if (!token) return;
			try {
				// Fetch available models
				const modelsResponse = await axios.get('/api/models', {
					headers: { Authorization: `Bearer ${token}` }
				});
				if (modelsResponse.data?.models) {
					setAvailableModels(modelsResponse.data.models);
				}

				// Fetch user settings
				const userResponse = await axios.get('/api/auth/users/me', {
					headers: { Authorization: `Bearer ${token}` }
				});
				const userData = userResponse.data;

				// Fetch system config for defaults
				const configResponse = await axios.get('/api/config', {
					headers: { Authorization: `Bearer ${token}` }
				});
				const configData = configResponse.data;

				setSettings(prev => ({
					...prev,
					llmModel1: userData.llm_model || configData.llm_model,
					llmModel2: userData.llm_side_model || configData.llm_side_model,
					embeddingModel: configData.embedding_model,
					rerankerModel: configData.reranker_model,
					// We don't get the actual API keys back for security, but we might want to know if they are set?
					// For now, let's leave them empty in UI or handle it differently if needed.
					// The user wants to input them.
				}));

			} catch (error: any) {
				if (error.response?.status === 401) {
					logout();
					return;
				}
				console.error('Failed to fetch settings data:', error);
			}
		};

		fetchData();
	}, [token]);

	const updateSettings = async (newSettings: Partial<Settings>, shouldPersist = true) => {
		setSettings((prev) => {
			const updated = { ...prev, ...newSettings };
			return updated;
		});

		if (!shouldPersist) return;

		// If relevant fields changed, update user profile
		if (newSettings.llmModel1 !== undefined ||
			newSettings.llmModel2 !== undefined ||
			newSettings.apiKey !== undefined ||
			newSettings.sideApiKey !== undefined) {

			if (!token) return;

			try {
				const updatePayload: any = {};
				if (newSettings.llmModel1 !== undefined) updatePayload.llm_model = newSettings.llmModel1;
				if (newSettings.llmModel2 !== undefined) updatePayload.llm_side_model = newSettings.llmModel2;
				if (newSettings.apiKey !== undefined) updatePayload.api_key = newSettings.apiKey;
				if (newSettings.sideApiKey !== undefined) updatePayload.side_api_key = newSettings.sideApiKey;

				await axios.put('/api/auth/users/me', updatePayload, {
					headers: { Authorization: `Bearer ${token}` }
				});
			} catch (error: any) {
				if (error.response?.status === 401) {
					logout();
					return;
				}
				console.error('Failed to update user settings:', error);
			}
		}
	};

	return { settings, updateSettings, availableModels };
}
