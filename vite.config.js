import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
const backend='http://127.0.0.1:'+(process.env.CLIP_PORT || '8766');
export default defineConfig({plugins:[react(),tailwindcss()],server:{proxy:{'/api':backend,'/media':backend}}});
