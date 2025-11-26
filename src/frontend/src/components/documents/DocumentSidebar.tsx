import { useRef } from 'react';
import { FileText, Upload, Trash2, Loader2, File, AlertCircle } from 'lucide-react';
import { useDocuments } from '../../hooks/useDocuments';


export function DocumentSidebar() {
	const { documents, uploadDocument, deleteDocument, isLoading } = useDocuments();
	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) {
			uploadDocument(file);
		}
	};

	return (
		<div className="w-80 bg-surface-50 dark:bg-surface-950 flex flex-col h-full transition-colors duration-300 border-l border-surface-200 dark:border-surface-800">
			{/* Header - Fixed Height for Alignment */}
			<div className="h-20 flex items-center justify-between px-6 shrink-0">
				<h2 className="font-bold text-lg text-surface-900 dark:text-surface-100 flex items-center gap-3">
					<div className="p-2 bg-primary-100 dark:bg-primary-500/10 rounded-xl">
						<FileText className="w-5 h-5 text-primary-600 dark:text-primary-400" />
					</div>
					Documents
				</h2>
				<span className="text-xs font-bold px-3 py-1.5 rounded-full bg-surface-200 dark:bg-surface-800 text-surface-700 dark:text-surface-300">
					{documents.length}
				</span>
			</div>

			<div className="flex-1 overflow-y-auto p-6 space-y-6">
				{/* Upload Area */}
				<div
					onClick={() => fileInputRef.current?.click()}
					onDragOver={(e) => {
						e.preventDefault();
						e.stopPropagation();
						e.currentTarget.classList.add('border-primary-500', 'bg-primary-50', 'dark:bg-primary-500/10');
					}}
					onDragLeave={(e) => {
						e.preventDefault();
						e.stopPropagation();
						e.currentTarget.classList.remove('border-primary-500', 'bg-primary-50', 'dark:bg-primary-500/10');
					}}
					onDrop={(e) => {
						e.preventDefault();
						e.stopPropagation();
						e.currentTarget.classList.remove('border-primary-500', 'bg-primary-50', 'dark:bg-primary-500/10');
						const file = e.dataTransfer.files?.[0];
						if (file) {
							uploadDocument(file);
						}
					}}
					className="border-2 border-dashed border-surface-300 dark:border-surface-700 rounded-[2rem] p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:border-primary-500 dark:hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-500/5 transition-all duration-300 group"
				>
					<input
						type="file"
						ref={fileInputRef}
						className="hidden"
						accept=".pdf,.md,.docx"
						onChange={handleFileChange}
					/>
					<div className="w-14 h-14 bg-primary-100 dark:bg-primary-500/20 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 group-hover:rotate-3 transition-all duration-300">
						<Upload className="w-7 h-7 text-primary-600 dark:text-primary-400" />
					</div>
					<p className="font-semibold text-surface-700 dark:text-surface-300">Upload Documents</p>
					<p className="text-xs text-surface-500 dark:text-surface-500 mt-1">50mb max.</p>
					<div className="flex gap-2 mt-3">
						<span className="text-[10px] font-mono bg-surface-200 dark:bg-surface-800 px-2 py-1 rounded-md text-surface-600 dark:text-surface-400">PDF</span>
						<span className="text-[10px] font-mono bg-surface-200 dark:bg-surface-800 px-2 py-1 rounded-md text-surface-600 dark:text-surface-400">MD</span>
						<span className="text-[10px] font-mono bg-surface-200 dark:bg-surface-800 px-2 py-1 rounded-md text-surface-600 dark:text-surface-400">DOCX</span>
					</div>
				</div>

				{/* Document List */}
				<div className="space-y-3">
					{isLoading && (
						<div className="flex items-center justify-center py-8 text-surface-400">
							<Loader2 className="w-6 h-6 animate-spin text-primary-500" />
						</div>
					)}

					{documents.map((doc) => (
						<div
							key={doc.id}
							className={`group flex items-center justify-between p-4 rounded-2xl bg-white dark:bg-surface-900 hover:shadow-md border border-transparent hover:border-surface-200 dark:hover:border-surface-700 transition-all duration-300 ${doc.status === 'failed' ? 'border-red-200 dark:border-red-900/30 bg-red-50/50 dark:bg-red-900/10' : ''
								}`}
						>
							<div className="flex items-center gap-4 min-w-0">
								<div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors ${doc.status === 'pending' || doc.status === 'processing'
									? 'bg-primary-100 dark:bg-primary-500/20 text-primary-600 dark:text-primary-400'
									: doc.status === 'failed'
										? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
										: 'bg-surface-100 dark:bg-surface-800 text-surface-500 dark:text-surface-400 group-hover:text-primary-500 dark:group-hover:text-primary-400'
									}`}>
									{doc.status === 'pending' || doc.status === 'processing' ? (
										<Loader2 className="w-5 h-5 animate-spin" />
									) : doc.status === 'failed' ? (
										<AlertCircle className="w-5 h-5" />
									) : (
										<File className="w-5 h-5" />
									)}
								</div>
								<div className="flex flex-col min-w-0">
									<span className="text-sm text-surface-700 dark:text-surface-300 truncate font-medium">{doc.filename}</span>
									{doc.status === 'processing' && (
										<span className="text-xs text-primary-500 font-medium animate-pulse">Processing...</span>
									)}
									{doc.status === 'pending' && (
										<span className="text-xs text-surface-400">Queued...</span>
									)}
									{doc.status === 'failed' && (
										<span className="text-xs text-red-500 truncate" title={doc.error_message}>
											Failed: {doc.error_message}
										</span>
									)}
								</div>
							</div>
							<button
								onClick={() => deleteDocument(doc.filename)}
								disabled={doc.status === 'processing' || doc.status === 'pending'}
								className={`p-2 rounded-xl transition-all duration-200 ${doc.status === 'processing' || doc.status === 'pending'
									? 'opacity-0 cursor-not-allowed'
									: 'opacity-0 group-hover:opacity-100 text-surface-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10'
									}`}
								title="Delete document"
							>
								<Trash2 className="w-4 h-4" />
							</button>
						</div>
					))}

					{documents.length === 0 && !isLoading && (
						<div className="text-center py-12 text-surface-400 dark:text-surface-500">
							<p className="text-sm">No documents uploaded yet</p>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
