import { useSettings } from '../hooks/useSettings';
import { Settings as SettingsIcon, Thermometer, Shield, Sliders, Database, Info, Zap } from 'lucide-react';

export function SettingsPage() {
	const { settings, updateSettings } = useSettings();

	const getSliderStyle = (value: number, min: number, max: number) => {
		const percentage = ((value - min) / (max - min)) * 100;
		return {
			background: `linear-gradient(to right, var(--color-primary-500) 0%, var(--color-primary-500) ${percentage}%, #e5e7eb ${percentage}%, #e5e7eb 100%)`
		};
	};

	return (
		<div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-8 transition-colors duration-300">
			<div className="max-w-2xl mx-auto space-y-8">
				<div className="flex items-center gap-3 pb-6 border-b border-gray-200 dark:border-gray-800">
					<div className="p-2 bg-primary-100 dark:bg-primary-500/10 rounded-lg">
						<SettingsIcon className="w-6 h-6 text-primary-600 dark:text-primary-400" />
					</div>
					<h1 className="text-2xl font-bold">Application Settings</h1>
				</div>

				{/* Models Configuration */}
				<div className="space-y-6">
					<h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
						<Database className="w-5 h-5 text-primary-500" />
						Model Configuration
					</h3>

					<div className="grid gap-4">
						<div className="space-y-2">
							<label className="text-sm font-medium text-gray-700 dark:text-gray-300">Main LLM Model</label>
							<div className="px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 font-mono text-sm">
								{settings.llmModel1 || 'Loading...'}
							</div>
						</div>

						<div className="space-y-2">
							<label className="text-sm font-medium text-gray-700 dark:text-gray-300">Secondary LLM Model</label>
							<div className="px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 font-mono text-sm">
								{settings.llmModel2 || 'Loading...'}
							</div>
						</div>

						<div className="space-y-2">
							<label className="text-sm font-medium text-gray-700 dark:text-gray-300">Embedding Model</label>
							<div className="px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 font-mono text-sm">
								{settings.embeddingModel || 'Loading...'}
							</div>
						</div>

						<div className="space-y-2">
							<label className="text-sm font-medium text-gray-700 dark:text-gray-300">Reranker Model</label>
							<div className="px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 font-mono text-sm">
								{settings.rerankerModel || 'Loading...'}
							</div>
						</div>
					</div>

					<div className="p-4 bg-primary-50 dark:bg-primary-900/20 rounded-xl border border-primary-100 dark:border-primary-800 flex gap-3">
						<Info className="w-5 h-5 text-primary-600 dark:text-primary-400 shrink-0" />
						<p className="text-sm text-primary-700 dark:text-primary-300">
							Model configuration is managed by the backend environment. To change these models, please update the server configuration.
						</p>
					</div>
				</div>

				{/* RAG Behavior Section */}
				<section className="space-y-6">
					<h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
						<Zap className="w-5 h-5 text-yellow-500" />
						RAG Behavior
					</h2>

					<div className="p-6 bg-white dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-800 space-y-6">
						{/* Strict Mode */}
						<div className="flex items-center justify-between">
							<div className="space-y-1">
								<div className="flex items-center gap-2">
									<Shield className="w-4 h-4 text-emerald-600 dark:text-emerald-500" />
									<span className="font-medium">Strict RAG Mode</span>
								</div>
								<p className="text-sm text-gray-600 dark:text-gray-400">Restrict answers to provided documents only</p>
							</div>
							<label className="relative inline-flex items-center cursor-pointer">
								<input
									type="checkbox"
									className="sr-only peer"
									checked={settings.strictMode}
									onChange={(e) => updateSettings({ strictMode: e.target.checked })}
								/>
								<div className="w-11 h-6 bg-gray-300 dark:bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
							</label>
						</div>

						{/* Temperature */}
						<div className="space-y-3">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Thermometer className="w-4 h-4 text-orange-600 dark:text-orange-500" />
									<span className="font-medium">Temperature</span>
								</div>
								<span className="text-sm font-mono bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded text-gray-700 dark:text-gray-300">
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
								className="w-full h-2 rounded-lg appearance-none cursor-pointer"
							/>
							<p className="text-xs text-gray-500 dark:text-gray-500">Controls randomness: Lower values are more deterministic</p>
						</div>

						{/* Rerank Threshold */}
						<div className="space-y-3 pt-4 border-t border-gray-200 dark:border-gray-700/50">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Sliders className="w-4 h-4 text-purple-600 dark:text-purple-500" />
									<span className="font-medium">Reranker Threshold</span>
								</div>
								<span className="text-sm font-mono bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded text-gray-700 dark:text-gray-300">
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
								className="w-full h-2 rounded-lg appearance-none cursor-pointer"
							/>
							<p className="text-xs text-gray-500 dark:text-gray-500">Minimum score for retrieved documents to be included</p>
						</div>
					</div>
				</section>
			</div>
		</div>
	);
}
