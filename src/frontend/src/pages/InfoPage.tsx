import { Info, Server, Database, Shield, Activity, type LucideIcon } from 'lucide-react';

export function InfoPage() {
	return (
		<div className="h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
			{/* Header */}
			<div className="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
				<h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-2">
					<Info className="w-5 h-5 text-primary-600 dark:text-primary-400" />
					About This Project
				</h2>
			</div>

			<div className="p-8 max-w-4xl mx-auto space-y-8">
				{/* Hero Section */}
				<div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-sm border border-gray-200 dark:border-gray-700">
					<h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
						Document-Grounded Conversational Assistant
					</h1>
					<p className="text-lg text-gray-600 dark:text-gray-300 leading-relaxed">
						This project is a <strong>production-ready boilerplate</strong> for a multi-tenant,
						document-grounded conversational assistant (RAG). It is built on a modern, cloud-native
						architecture designed for scalability, observability, and flexibility.
					</p>
				</div>

				{/* Key Features Grid */}
				<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
					<FeatureCard
						icon={Server}
						title="Cloud-Agnostic Design"
						description="Uses S3-compatible object storage and PostgreSQL, allowing for seamless deployment to AWS, GCP, Azure, or on-premise."
					/>
					<FeatureCard
						icon={Activity}
						title="Advanced RAG Pipeline"
						description="Features a sophisticated retrieval workflow with query expansion, Parent Document Retrieval (PDR), and Cross-Encoder re-ranking."
					/>
					<FeatureCard
						icon={Shield}
						title="Secure Multi-Tenancy"
						description="Built-in authentication with JWT, ensuring strict data isolation between users for both documents and vector indices."
					/>
					<FeatureCard
						icon={Database}
						title="Deep Observability"
						description="Integrated with Prometheus & Grafana for real-time metrics, and LangSmith for end-to-end tracing and evaluation."
					/>
				</div>

				{/* Tech Stack Section */}
				<div className="bg-primary-50 dark:bg-primary-900/20 rounded-2xl p-8 border border-primary-100 dark:border-primary-800">
					<h3 className="text-xl font-bold text-gray-900 dark:text-white mb-6">Core Technologies</h3>
					<div className="flex flex-wrap gap-3">
						{['Docker', 'LangChain', 'FastAPI', 'LiteLLM', 'PostgreSQL', 'PGVector', 'Minio', 'Nginx', 'Redis', 'Prometheus', 'Grafana', 'LangSmith', 'Tailwind CSS', 'React'].map((tech) => (
							<span key={tech} className="px-3 py-1 bg-white dark:bg-gray-800 text-primary-700 dark:text-primary-300 rounded-full text-sm font-medium shadow-sm border border-primary-100 dark:border-primary-700">
								{tech}
							</span>
						))}
					</div>
				</div>

				{/* Footer */}
				<div className="text-center text-gray-500 dark:text-gray-400 pt-8">
					<p>
						For a complete technical overview, check out the{' '}
						<a
							href="https://github.com/kpoilly/RAG-Boilerplate"
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary-600 dark:text-primary-400 hover:underline font-medium"
						>
							GitHub repository
						</a>
						.
					</p>
				</div>
			</div>
		</div>
	);
}



function FeatureCard({ icon: Icon, title, description }: { icon: LucideIcon, title: string, description: string }) {
	return (
		<div className="bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition-shadow">
			<div className="w-10 h-10 bg-primary-100 dark:bg-primary-900/50 rounded-lg flex items-center justify-center mb-4">
				<Icon className="w-5 h-5 text-primary-600 dark:text-primary-400" />
			</div>
			<h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{title}</h3>
			<p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed">{description}</p>
		</div>
	);
}
