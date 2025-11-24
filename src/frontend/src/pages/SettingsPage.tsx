import { useSettings } from '../hooks/useSettings';
import { Settings as SettingsIcon, Thermometer, Shield, Sliders, Database, Info, Zap, Eye, EyeOff } from 'lucide-react';
import { CustomSelect } from '../components/ui/CustomSelect';
import { useState } from 'react';

interface ApiKeyInputProps {
	value: string;
	onChange: (value: string) => void;
	onBlur?: (value: string) => void;
	placeholder?: string;
	disabled?: boolean;
}

function ApiKeyInput({ value, onChange, onBlur, placeholder, disabled }: ApiKeyInputProps) {
	const [showPassword, setShowPassword] = useState(false);
	const isShort = value.length < 10;
	const inputType = isShort || showPassword ? 'text' : 'password';

	return (
		<div className="relative">
			<input
				type={inputType}
				value={value}
				onChange={(e) => onChange(e.target.value)}
				onBlur={(e) => onBlur?.(e.target.value)}
				placeholder={placeholder}
				disabled={disabled}
				className="w-full px-5 py-4 pr-12 bg-surface-50 dark:bg-surface-950 rounded-[1.5rem] border border-surface-200 dark:border-surface-800 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50 transition-all"
			/>
			<button
				type="button"
				onClick={() => setShowPassword(!showPassword)}
				disabled={disabled}
				className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 transition-colors"
			>
				{showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
			</button>
		</div>
	);
}

export function SettingsPage() {
	const { settings, updateSettings, availableModels, maskedApiKey, maskedSideApiKey } = useSettings();

	const getSliderStyle = (value: number, min: number, max: number) => {
		const percentage = ((value - min) / (max - min)) * 100;
		return {
			background: `linear-gradient(to right, var(--color-primary-500) 0%, var(--color-primary-500) ${percentage}%, #e5e7eb ${percentage}%, #e5e7eb 100%)`
		};
	};

	const getApiKeyPlaceholder = (model: string) => {
		if (model.includes('groq')) return 'gsk_...';
		else if (model.includes('openai') || model.includes('gpt')) return 'sk_...';
		else if (model.includes('anthropic')) return 'sk-ant_...';
		else return 'API key...';
	};

	// Use masked keys as placeholders if available, otherwise use default placeholders
	const main_key_placeholder = maskedApiKey || getApiKeyPlaceholder(settings.llmModel1);
	const side_key_placeholder = maskedSideApiKey || getApiKeyPlaceholder(settings.llmModel2);

	return (
		<div className="flex-1 overflow-y-auto bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-50 p-8 transition-colors duration-300">
			<div className="max-w-3xl mx-auto space-y-8">
				<div className="flex items-center gap-4 pb-6">
					<div className="p-3 bg-primary-100 dark:bg-primary-500/10 rounded-2xl">
						<SettingsIcon className="w-8 h-8 text-primary-600 dark:text-primary-400" />
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Settings</h1>
						<p className="text-surface-500 dark:text-surface-400">Manage your AI preferences</p>
					</div>
				</div>

				{/* Models Configuration */}
				<div className="space-y-6">
					<h3 className="text-xl font-semibold text-surface-900 dark:text-surface-100 flex items-center gap-2 ml-2">
						<Database className="w-5 h-5 text-primary-500" />
						Model Configuration
					</h3>

					<div className="grid gap-6 grid-cols-1">
						{/* Main Model */}
						<div className="space-y-4 p-5 bg-white dark:bg-surface-900 rounded-[2rem] border border-surface-200 dark:border-surface-800 shadow-sm">
							<CustomSelect
								label="Main LLM Model"
								value={settings.llmModel1}
								onChange={(value) => {
									updateSettings({ llmModel1: value, apiKey: '' });
								}}
								options={availableModels.map(m => ({ value: m.model_id, label: m.model_name }))}
								placeholder="Select a model"
							/>
							<div className="space-y-2">
								<label className="text-sm font-bold text-surface-700 dark:text-surface-300 ml-1">API Key</label>
								<ApiKeyInput
									value={settings.apiKey}
									onChange={(value) => updateSettings({ apiKey: value }, false)}
									onBlur={(value) => updateSettings({ apiKey: value }, true)}
									placeholder={main_key_placeholder}
								/>
							</div>
						</div>

						{/* Secondary Model */}
						<div className={`space-y-4 p-5 bg-white dark:bg-surface-900 rounded-[2rem] border border-surface-200 dark:border-surface-800 shadow-sm transition-opacity duration-300 ${settings.useMainAsSide ? 'opacity-50 pointer-events-none' : ''}`}>
							<CustomSelect
								label="Secondary LLM Model"
								value={settings.llmModel2}
								onChange={(value) => {
									updateSettings({ llmModel2: value, sideApiKey: '' });
								}}
								options={availableModels.map(m => ({ value: m.model_id, label: m.model_name }))}
								disabled={settings.useMainAsSide}
								placeholder="Select a model"
							/>
							<div className="space-y-2">
								<label className="text-sm font-bold text-surface-700 dark:text-surface-300 ml-1">Side API Key</label>
								<ApiKeyInput
									value={settings.sideApiKey}
									onChange={(value) => updateSettings({ sideApiKey: value }, false)}
									onBlur={(value) => updateSettings({ sideApiKey: value }, true)}
									placeholder={side_key_placeholder}
									disabled={settings.useMainAsSide}
								/>
							</div>
						</div>
					</div>

					{/* Use Main as Side Toggle */}
					<div className="flex items-center gap-3 ml-2">
						<label className="relative inline-flex items-center cursor-pointer">
							<input
								type="checkbox"
								className="sr-only peer"
								checked={settings.useMainAsSide}
								onChange={(e) => {
									const checked = e.target.checked;
									updateSettings({
										useMainAsSide: checked,
										llmModel2: checked ? settings.llmModel1 : settings.llmModel2,
										sideApiKey: checked ? settings.apiKey : settings.sideApiKey
									});
								}}
							/>
							<div className="w-11 h-6 bg-surface-200 dark:bg-surface-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500 transition-colors"></div>
						</label>
						<span className="text-sm font-medium text-surface-700 dark:text-surface-300">Use Main Model configuration for Secondary Model</span>
					</div>

					<div className="p-5 bg-primary-50 dark:bg-primary-900/20 rounded-[1.5rem] border border-primary-100 dark:border-primary-800 flex gap-4 items-start">
						<Info className="w-5 h-5 text-primary-600 dark:text-primary-400 shrink-0 mt-0.5" />
						<p className="text-sm text-primary-700 dark:text-primary-300 leading-relaxed">
							API Keys are encrypted and stored securely. They are only used for your requests.
						</p>
					</div>
				</div>

				{/* RAG Behavior Section */}
				<section className="space-y-6">
					<h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 flex items-center gap-2 ml-2">
						<Zap className="w-5 h-5 text-accent-500" />
						RAG Behavior
					</h2>

					<div className="p-8 bg-white dark:bg-surface-900 rounded-[2rem] border border-surface-200 dark:border-surface-800 shadow-sm space-y-8">
						{/* Strict Mode */}
						<div className="flex items-center justify-between">
							<div className="space-y-1">
								<div className="flex items-center gap-2">
									<Shield className="w-5 h-5 text-emerald-500" />
									<span className="font-medium text-lg">Strict RAG Mode</span>
								</div>
								<p className="text-surface-500 dark:text-surface-400">Restrict answers to provided documents only</p>
							</div>
							<label className="relative inline-flex items-center cursor-pointer">
								<input
									type="checkbox"
									className="sr-only peer"
									checked={settings.strictMode}
									onChange={(e) => updateSettings({ strictMode: e.target.checked })}
								/>
								<div className="w-14 h-8 bg-surface-200 dark:bg-surface-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[4px] after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-primary-500 transition-colors"></div>
							</label>
						</div>

						{/* Temperature */}
						<div className="space-y-4">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Thermometer className="w-5 h-5 text-accent-500" />
									<span className="font-medium text-lg">Temperature</span>
								</div>
								<span className="text-sm font-mono font-bold bg-surface-100 dark:bg-surface-800 px-3 py-1 rounded-lg text-surface-700 dark:text-surface-300">
									{settings.temperature}
								</span>
							</div>
							<input
								type="range"
								min="0"
								max="2"
								step="0.05"
								value={settings.temperature}
								onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
								style={getSliderStyle(settings.temperature, 0, 2)}
								className="w-full h-3 rounded-full appearance-none cursor-pointer accent-primary-500"
							/>
							<p className="text-sm text-surface-500 dark:text-surface-400">Controls randomness: Lower values are more deterministic</p>
						</div>

						{/* Rerank Threshold */}
						<div className="space-y-4 pt-6 border-t border-surface-100 dark:border-surface-800">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Sliders className="w-5 h-5 text-purple-500" />
									<span className="font-medium text-lg">Reranker Threshold</span>
								</div>
								<span className="text-sm font-mono font-bold bg-surface-100 dark:bg-surface-800 px-3 py-1 rounded-lg text-surface-700 dark:text-surface-300">
									{settings.rerankThreshold}
								</span>
							</div>
							<input
								type="range"
								min="-10"
								max="10"
								step="0.05"
								value={settings.rerankThreshold}
								onChange={(e) => updateSettings({ rerankThreshold: parseFloat(e.target.value) })}
								style={getSliderStyle(settings.rerankThreshold, -10, 10)}
								className="w-full h-3 rounded-full appearance-none cursor-pointer accent-primary-500"
							/>
							<p className="text-sm text-surface-500 dark:text-surface-400">Minimum score for retrieved documents to be included</p>
						</div>
					</div>
				</section>
			</div>
		</div>
	);
}
