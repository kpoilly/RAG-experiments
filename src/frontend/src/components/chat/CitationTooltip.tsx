import * as Tooltip from '@radix-ui/react-tooltip';
import type { Source } from '../../types';

interface CitationTooltipProps {
	source: Source;
}

function formatChunk(text: string): string {
	// Remove badly placed line breaks (not after period, not before capital letter)
	text = text.replace(/(?<!\n)(?<!\.)(\n)(?!\n)(?![A-Z])/g, ' ');
	text = text.trim();

	// Find first capital letter and start from there (remove incomplete sentences at start)
	const matchStart = text.match(/[A-Z]/);
	if (matchStart && matchStart.index !== undefined) {
		text = text.substring(matchStart.index);
	} else {
		return text;
	}

	// Find last period and cut after it (remove incomplete sentences at end)
	const lastPeriodIndex = text.lastIndexOf('.');
	if (lastPeriodIndex !== -1) {
		text = text.substring(0, lastPeriodIndex + 1);
	}

	return text;
}

export function CitationTooltip({ source }: CitationTooltipProps) {
	const formattedContent = formatChunk(source.content);

	return (
		<Tooltip.Provider delayDuration={200}>
			<Tooltip.Root>
				<Tooltip.Trigger asChild>
					<span className="inline-flex items-center justify-center w-5 h-5 ml-1 text-xs font-medium text-primary-600 dark:text-primary-400 bg-primary-50 dark:bg-primary-500/10 rounded cursor-help hover:bg-primary-100 dark:hover:bg-primary-500/20 transition-colors border border-primary-200 dark:border-primary-500/20">
						{source.index}
					</span>
				</Tooltip.Trigger>
				<Tooltip.Portal>
					<Tooltip.Content
						className="z-50 max-w-md p-4 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg text-gray-900 dark:text-gray-200 animate-in fade-in zoom-in-95 duration-200"
						sideOffset={5}
					>
						<div className="flex flex-col gap-2">
							<div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
								<span className="font-semibold text-primary-600 dark:text-primary-400">{source.source}</span>
								{source.page && <span className="text-xs text-gray-500 dark:text-gray-500">Page {source.page}</span>}
							</div>
							<p className="text-gray-700 dark:text-gray-300 leading-relaxed text-xs">
								{formattedContent}
							</p>
						</div>
						<Tooltip.Arrow className="fill-white dark:fill-gray-800" />
					</Tooltip.Content>
				</Tooltip.Portal>
			</Tooltip.Root>
		</Tooltip.Provider>
	);
}
