import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './useAuth';

export interface Document {
	id: string;
	filename: string;
	status: 'pending' | 'processing' | 'completed' | 'failed';
	created_at: string;
	error_message?: string;
}

export function useDocuments() {
	const [documents, setDocuments] = useState<Document[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const { token, logout } = useAuth();

	const fetchDocuments = useCallback(async () => {
		if (!token) return;
		try {
			const response = await axios.get<Document[]>('/api/documents', {
				headers: { Authorization: `Bearer ${token}` }
			});
			setDocuments(response.data);
		} catch (error: any) {
			if (error.response?.status === 401) {
				logout();
				return;
			}
			console.error('Failed to fetch documents', error);
		}
	}, [token, logout]);

	const uploadDocument = async (file: File) => {
		if (!token) return;

		const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
		if (file.size > MAX_FILE_SIZE) {
			alert(`File is too large. Maximum size is 50MB. Your file is ${(file.size / (1024 * 1024)).toFixed(2)}MB.`);
			return;
		}

		setIsLoading(true);
		const formData = new FormData();
		formData.append('file', file);
		try {
			await axios.post('/api/documents', formData, {
				headers: { Authorization: `Bearer ${token}` }
			});
			await fetchDocuments();
		} catch (error: any) {
			if (error.response?.status === 401) {
				logout();
				return;
			}
			console.error('Failed to upload document', error);
		} finally {
			setIsLoading(false);
		}
	};

	const deleteDocument = async (filename: string) => {
		if (!token) return;
		try {
			await axios.delete(`/api/documents/${filename}`, {
				headers: { Authorization: `Bearer ${token}` }
			});
			await fetchDocuments();
		} catch (error: any) {
			if (error.response?.status === 401) {
				logout();
				return;
			}
			console.error('Failed to delete document', error);
		}
	};

	useEffect(() => {
		fetchDocuments();

		// Poll for updates if any document is pending or processing
		const interval = setInterval(() => {
			setDocuments(currentDocs => {
				const hasPending = currentDocs.some(doc => doc.status === 'pending' || doc.status === 'processing');
				if (hasPending) {
					return currentDocs;
				}
				return currentDocs;
			});
		}, 3000);

		return () => clearInterval(interval);
	}, []);

	useEffect(() => {
		const hasPending = documents.some(doc => doc.status === 'pending' || doc.status === 'processing');

		let intervalId: any;
		if (hasPending) {
			intervalId = setInterval(() => {
				fetchDocuments();
			}, 3000);
		}

		return () => {
			if (intervalId) clearInterval(intervalId);
		};
	}, [documents, fetchDocuments]);
	return { documents, uploadDocument, deleteDocument, isLoading };
}
