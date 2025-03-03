import React from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import Dashboard from './components/Dashboard';

function ErrorFallback({error}: {error: Error}) {
  return (
    <div role="alert" style={{padding: '20px'}}>
      <p>Something went wrong:</p>
      <pre style={{color: 'red'}}>{error.message}</pre>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <div className="min-h-screen bg-gray-100">
        <Dashboard />
      </div>
    </ErrorBoundary>
  );
}

export default App;