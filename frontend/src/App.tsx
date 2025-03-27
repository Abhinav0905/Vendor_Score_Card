import React from 'react';
import { CssBaseline } from '@mui/material';
import { ErrorBoundary } from 'react-error-boundary';
import Dashboard from './components/Dashboard';

function ErrorFallback({error}: {error: Error}) {
  return (
    <div role="alert" style={{
      padding: '20px',
      margin: '20px',
      borderRadius: '8px',
      backgroundColor: '#fee2e2',
      border: '1px solid #ef4444'
    }}>
      <h3 style={{color: '#dc2626', marginBottom: '10px'}}>Something went wrong</h3>
      <pre style={{
        color: '#7f1d1d',
        backgroundColor: '#fecaca',
        padding: '10px',
        borderRadius: '4px',
        overflow: 'auto'
      }}>{error.message}</pre>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <CssBaseline />
      <div className="min-h-screen bg-gray-100">
        <Dashboard />
      </div>
    </ErrorBoundary>
  );
}

export default App;