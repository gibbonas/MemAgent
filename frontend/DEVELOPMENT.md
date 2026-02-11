# Frontend Development Guide

## Quick Start

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) (or 3001 if 3000 is in use).

## Development Workflow

### Making Changes

1. Edit files in `app/`, `components/`, or `lib/`
2. Save the file - Next.js will auto-reload
3. Check the browser for changes

### Adding New Components

Create new components in `components/`:

```typescript
// components/MyComponent.tsx
'use client'

interface MyComponentProps {
  // props here
}

export default function MyComponent({ }: MyComponentProps) {
  return (
    <div>My Component</div>
  )
}
```

### Adding New API Endpoints

Add functions to `lib/api.ts`:

```typescript
export const myNewEndpoint = async (param: string) => {
  const response = await api.get(`/api/my-endpoint?param=${param}`)
  return response.data
}
```

## Common Tasks

### Updating Styles

Edit `app/globals.css` for global styles or use Tailwind classes inline:

```tsx
<div className="bg-blue-500 text-white p-4 rounded-lg">
  Styled with Tailwind
</div>
```

### Adding Dependencies

```bash
npm install package-name
npm install --save-dev @types/package-name  # if TypeScript types needed
```

### Checking for Errors

```bash
npm run lint
```

### Building for Production

```bash
npm run build
npm run start
```

## Debugging

### Browser DevTools

1. Open Chrome/Edge DevTools (F12)
2. Check Console for errors
3. Use Network tab to inspect API calls
4. Use React DevTools extension for component inspection

### Common Issues

**Port already in use:**
- Next.js will automatically try port 3001, 3002, etc.
- Or manually specify: `npm run dev -- -p 3005`

**API not connecting:**
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Ensure backend is running on port 8000
- Check CORS settings in backend

**TypeScript errors:**
- Run `npm run build` to see all type errors
- Check `tsconfig.json` for configuration

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout (metadata, fonts)
│   ├── page.tsx            # Home page (auth + chat)
│   └── globals.css         # Global styles
├── components/
│   ├── AuthButton.tsx      # OAuth button
│   └── ChatInterface.tsx   # Main chat UI
├── lib/
│   └── api.ts              # API client
├── public/                 # Static files
├── .env.local              # Environment variables
├── next.config.js          # Next.js config
├── tailwind.config.ts      # Tailwind config
└── tsconfig.json           # TypeScript config
```

## Best Practices

### Component Organization

- Keep components small and focused
- Use TypeScript interfaces for props
- Extract reusable logic to custom hooks

### State Management

- Use `useState` for local component state
- Use `useEffect` for side effects
- Store user data in localStorage for persistence

### API Calls

- Always handle errors with try/catch
- Show loading states during API calls
- Display user-friendly error messages

### Styling

- Use Tailwind utility classes
- Keep custom CSS minimal
- Follow mobile-first responsive design

## Testing

```bash
# Add testing libraries
npm install --save-dev @testing-library/react @testing-library/jest-dom jest jest-environment-jsdom

# Run tests (after setup)
npm test
```

## Performance

- Next.js automatically optimizes images
- Use dynamic imports for large components
- Minimize bundle size by removing unused dependencies

## Deployment

See main README.md for deployment instructions.
