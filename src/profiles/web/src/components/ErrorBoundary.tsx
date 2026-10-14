import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Application render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-app p-6 text-ink">
          <section className="w-full max-w-lg rounded-lg border border-line bg-surface p-6">
            <h1 className="text-base font-semibold">ProFiles encountered an error</h1>
            <p className="mt-2 text-sm text-ink-secondary">The interface could not continue. Reload the application to try again.</p>
            <details className="mt-4 text-xs text-ink-muted">
              <summary className="cursor-pointer">Error details</summary>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap">{this.state.error.message}</pre>
            </details>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-5 rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              Reload application
            </button>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}