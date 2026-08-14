import { defineConfig } from 'vite';

export default defineConfig({
  // GitHub Pages(https://<user>.github.io/jodo_reborn_v2/)配信用のベースパス
  base: '/jodo_reborn_v2/',
  build: {
    chunkSizeWarningLimit: 1500,
  },
});
