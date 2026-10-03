import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import CompanyTabBrand from './components/CompanyTabBrand';
import { applyCompanyTabBrand } from './utils/companyBranding';
import { applyAppearance, loadAppearanceSettings } from './utils/theme';
import './index.css';

applyAppearance(loadAppearanceSettings(null));
applyCompanyTabBrand(null);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppProvider>
            <CompanyTabBrand />
            <App />
          </AppProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
