/** @type {import('tailwindcss').Config} */
export default {
	darkMode: 'class',
	content: [
		"./index.html",
		"./src/**/*.{js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				// 🎨 Edit colors here with the color picker!
				// Then run: npm run sync-colors
				// This will auto-generate the @theme section in index.css
				primary: {
					50: '#e9f4f1ff',   // teal-50
					100: '#cae6e0ff',  // teal-100
					200: '#abe3d8ff',  // teal-200
					300: '#79d1c4ff',  // teal-300
					400: '#2dd4bf',  // teal-400
					500: '#14b8a6',  // teal-500 - Main brand color
					600: '#0d9488',  // teal-600
					700: '#0f766e',  // teal-700
					800: '#115e59',  // teal-800
					900: '#134e4a',  // teal-900
				},
				accent: {
					400: '#fb923c',  // orange-400 - For assistant icon
				},
			},
		},
	},
	plugins: [],
}
