export interface Source {
	index: number;
	page?: number;
	content: string;
	source: string;
}

export interface Message {
	role: 'user' | 'assistant';
	content: string;
	sources?: Source[];
}
