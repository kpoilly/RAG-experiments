import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './useAuth';

export function useDocuments() {
	const [documents, setDocuments] = useState<string[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const { token } = useAuth();

	const fetchDocuments = useCallback(async () => {
		if (!token) return;
		try {
			// Placeholder: In real app, this would be axios.get('/api/documents')
			// For now, return empty or mock
			const response = await axios.get('/api/documents', {
				headers: { Authorization: `Bearer ${token}` }
			});
			setDocuments(response.data);
		} catch (error) {
			console.error('Failed to fetch documents', error);
			// setDocuments(['manual.pdf', 'guidelines.docx']); // Mock
		}
	}, [token]);

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
		} catch (error) {
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
		} catch (error) {
			console.error('Failed to delete document', error);
		}
	};

	useEffect(() => {
		fetchDocuments();
	}, [fetchDocuments]);

	return { documents, uploadDocument, deleteDocument, isLoading };
}
