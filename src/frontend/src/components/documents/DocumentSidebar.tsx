import { useRef } from 'react';
import { FileText, Upload, Trash2, Loader2, File } from 'lucide-react';
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
		<div className="w-80 border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col h-full transition-colors duration-300">
			{/* Header - Fixed Height for Alignment */}
			<div className="h-16 flex items-center justify-between px-6 border-b border-gray-200 dark:border-gray-800 shrink-0">
				<h2 className="font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-2">
					<FileText className="w-5 h-5 text-primary-600 dark:text-primary-400" />
					Documents
				</h2>
				<span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
					{documents.length}
				</span>
			</div>

			<div className="flex-1 overflow-y-auto p-4 space-y-4">
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
					className="border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer hover:border-primary-500 dark:hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-500/5 transition-all group"
				>
					<input
						type="file"
						ref={fileInputRef}
						className="hidden"
						accept=".pdf,.md,.docx"
						onChange={handleFileChange}
					/>
					<div className="w-10 h-10 bg-primary-100 dark:bg-primary-500/20 rounded-full flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
						<Upload className="w-5 h-5 text-primary-600 dark:text-primary-400" />
					</div>
					<p className="text-sm font-medium text-gray-700 dark:text-gray-300">Upload documents</p>
					<p className="text-xs text-gray-500 dark:text-gray-500 mt-1">Drag & drop or click to upload</p>
					<p className="text-[10px] text-gray-400 mt-1">PDF, MD, DOCX</p>
				</div>

				{/* Document List */}
				<div className="space-y-2">
					{isLoading && (
						<div className="flex items-center justify-center py-4 text-gray-400">
							<Loader2 className="w-5 h-5 animate-spin" />
						</div>
					)}

					{documents.map((doc) => (
						<div
							key={doc}
							className="group flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all"
						>
							<div className="flex items-center gap-3 min-w-0">
								<div className="w-8 h-8 rounded-lg bg-white dark:bg-gray-700 flex items-center justify-center shrink-0 border border-gray-200 dark:border-gray-600">
									<File className="w-4 h-4 text-gray-500 dark:text-gray-400" />
								</div>
								<span className="text-sm text-gray-700 dark:text-gray-300 truncate font-medium">{doc}</span>
							</div>
							<button
								onClick={() => deleteDocument(doc)}
								className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-md transition-all"
								title="Delete document"
							>
								<Trash2 className="w-4 h-4" />
							</button>
						</div>
					))}

					{documents.length === 0 && !isLoading && (
						<div className="text-center py-8 text-gray-400 dark:text-gray-500">
							<p className="text-sm">No documents uploaded yet</p>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
