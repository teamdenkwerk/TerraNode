import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { ErrorBoundary } from './components/ErrorBoundary';
// @ts-expect-error Leaflet does not provide TypeScript declarations for its CSS entrypoint.
import 'leaflet/dist/leaflet.css';
// @ts-expect-error The bundler handles the CSS import; TypeScript has no declaration for it.
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);