# ✨ Emoji Masterpiece

The Ultimate High-Fidelity Art Engine. This application converts your photos into beautiful mosaics made entirely of emojis.

## 🚀 Features

- **High Fidelity**: Up to 10 levels of detail for stunning results.
- **Glassmorphic UI**: Premium, modern interface with dark/light mode support.
- **Responsive**: Fully optimized for mobile, tablet, and desktop.
- **Real-time Processing**: Fast emoji generation with real-time feedback.
- **Advanced Export**: Download in PNG, JPG, or WEBP formats.

## 🛠️ Tech Stack

- **Frontend**: React, Vite, Framer Motion, Lucide Icons, Styled Components.
- **Backend**: Python, FastAPI/Flask, OpenCV, NumPy.

## 📦 Installation

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## 🌐 Deployment

### Frontend (Netlify/Vercel)
- **Build Command**: `npm run build`
- **Publish Directory**: `frontend/dist`
- **Environment Variables**: Set `VITE_API_URL` to your hosted backend URL.

### Backend (Render/Railway)
- Ensure the server allows CORS for your frontend domain.
- Set up directories: `uploads/` and `outputs/`.

## 📄 License
MIT
