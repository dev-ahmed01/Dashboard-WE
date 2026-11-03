import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({plugins:[react()],server:{proxy:{'/api':'http://localhost:8000','/site':'http://localhost:8000','/sitemap.xml':'http://localhost:8000','/robots.txt':'http://localhost:8000'}}})
