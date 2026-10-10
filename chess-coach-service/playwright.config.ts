import {defineConfig} from './frontend-react/node_modules/@playwright/test'
export default defineConfig({testDir:'./e2e',timeout:120000,use:{baseURL:process.env.BASE_URL||'http://127.0.0.1:18082',trace:'retain-on-failure'},reporter:'list'})
