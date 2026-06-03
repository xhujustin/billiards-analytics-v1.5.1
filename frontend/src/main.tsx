import ReactDOM from 'react-dom/client';
import App from './App';
import './i18n';

async function renderApp() {
  const root = ReactDOM.createRoot(document.getElementById('root')!);
  const params = new URLSearchParams(window.location.search);

  if (params.get('prototype') === 'mobile') {
    await import('./index.css');
    const { default: MobilePrototypeApp } = await import('./MobilePrototypeApp');
    root.render(<MobilePrototypeApp />);
    return;
  }

  root.render(<App />);
}

void renderApp();
