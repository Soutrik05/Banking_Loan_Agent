# Switching Render to Docker Deployment

1. Go to Render Dashboard → your backend service
2. Go to Settings → Build & Deploy
3. Change "Runtime" from "Python 3" to "Docker"
4. Set "Dockerfile Path" to: backend/Dockerfile
5. Set "Docker Build Context Directory" to: backend
6. Keep all existing Environment Variables (SUPABASE_URL,
   AZURE_OPENAI_API_KEY, etc.) — these carry over
7. Save and trigger manual deploy
8. Check build logs — should show "Installing tesseract-ocr"
   and "Installing poppler-utils" during build
9. Once deployed, verify by checking /health endpoint
