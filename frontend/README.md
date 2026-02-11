# MemAgent Frontend

Modern Next.js 14 chat interface for the MemAgent memory preservation system.

## Features

- 🎨 Modern, responsive UI with Tailwind CSS
- 💬 Real-time chat interface for memory collection
- 🔐 Google OAuth integration
- 📱 Mobile-friendly design
- ⚡ Fast page loads with Next.js App Router
- 🎯 TypeScript for type safety

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Axios** - HTTP client for API calls
- **Lucide React** - Beautiful icons
- **date-fns** - Date formatting

## Getting Started

### Prerequisites

- Node.js 18+ installed
- Backend server running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:3002`.

### Environment Variables

Create a `.env.local` file:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx       # Root layout with fonts
│   ├── page.tsx         # Home page with auth flow
│   └── globals.css      # Global styles
├── components/
│   ├── AuthButton.tsx   # Google OAuth button
│   └── ChatInterface.tsx # Main chat UI
├── lib/
│   └── api.ts           # API client functions
└── public/              # Static assets
```

## Features

### Authentication

- Google OAuth 2.0 flow
- Persistent session management
- Auto-reconnect on page reload

### Chat Interface

- Real-time message exchange
- Message history persistence
- Loading states and error handling
- Image preview for generated memories
- Status indicators (processing, completed, failed)

### API Integration

All backend endpoints integrated:
- `/api/auth/*` - Authentication
- `/api/chat/*` - Chat and sessions
- `/api/photos/*` - Photo management

## Development

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

### Code Style

- TypeScript strict mode enabled
- ESLint with Next.js recommended config
- Tailwind CSS for consistent styling

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

### Docker

Build and run with Docker:

```bash
docker build -t memagent-frontend .
docker run -p 3000:3000 memagent-frontend
```

### Environment Variables for Production

Set these in your deployment platform:

- `NEXT_PUBLIC_API_URL` - Backend API URL (e.g., `https://api.yourdomain.com`)

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

## License

Proprietary - All rights reserved
