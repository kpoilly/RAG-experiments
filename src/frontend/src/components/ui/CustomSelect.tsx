import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Option {
	value: string;
	label: string;
}

interface CustomSelectProps {
	value: string;
	onChange: (value: string) => void;
	options: Option[];
	placeholder?: string;
	disabled?: boolean;
	label?: string;
}

export const CustomSelect: React.FC<CustomSelectProps> = ({
	value,
	onChange,
	options,
	placeholder = 'Select an option',
	disabled = false,
	label
}) => {
	const [isOpen, setIsOpen] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);

	const selectedOption = options.find(opt => opt.value === value);

	useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
				setIsOpen(false);
			}
		};

		document.addEventListener('mousedown', handleClickOutside);
		return () => document.removeEventListener('mousedown', handleClickOutside);
	}, []);

	const handleSelect = (optionValue: string) => {
		onChange(optionValue);
		setIsOpen(false);
	};

	return (
		<div className="space-y-2" ref={containerRef}>
			{label && (
				<label className="text-sm font-bold text-surface-700 dark:text-surface-300 ml-1">
					{label}
				</label>
			)}
			<div className="relative">
				<button
					type="button"
					onClick={() => !disabled && setIsOpen(!isOpen)}
					disabled={disabled}
					className={`
						w-full px-5 py-4 flex items-center justify-between
						bg-surface-50 dark:bg-surface-950 
						rounded-[1.5rem] border 
						${isOpen ? 'border-primary-500 ring-2 ring-primary-500/20' : 'border-surface-200 dark:border-surface-800'}
						text-surface-900 dark:text-surface-100 
						transition-all duration-200
						${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-primary-400 dark:hover:border-primary-600'}
					`}
				>
					<span className={`block truncate ${!selectedOption ? 'text-surface-400' : ''}`}>
						{selectedOption ? selectedOption.label : placeholder}
					</span>
					<ChevronDown
						className={`w-5 h-5 text-surface-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
					/>
				</button>

				<AnimatePresence>
					{isOpen && !disabled && (
						<motion.div
							initial={{ opacity: 0, y: -10, scale: 0.95 }}
							animate={{ opacity: 1, y: 0, scale: 1 }}
							exit={{ opacity: 0, y: -10, scale: 0.95 }}
							transition={{ duration: 0.1 }}
							className="absolute z-50 w-full mt-2 py-2 bg-white dark:bg-surface-900 rounded-[1.5rem] border border-surface-200 dark:border-surface-800 shadow-xl max-h-60 overflow-auto"
						>
							{options.map((option) => (
								<button
									key={option.value}
									type="button"
									onClick={() => handleSelect(option.value)}
									className={`
										w-full px-5 py-3 text-left flex items-center justify-between
										transition-colors duration-150
										${option.value === value
											? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 font-medium'
											: 'text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800'}
									`}
								>
									<span className="truncate">{option.label}</span>
									{option.value === value && (
										<Check className="w-4 h-4 text-primary-500" />
									)}
								</button>
							))}
						</motion.div>
					)}
				</AnimatePresence>
			</div>
		</div>
	);
};
