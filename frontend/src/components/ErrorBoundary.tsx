import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('TERRANODE UI Error caught by boundary:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReset = () => {
    localStorage.removeItem('terranode_admin_session');
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#F6F2EB] flex items-center justify-center p-6 text-[#241D16]">
          <div className="max-w-lg w-full bg-white rounded-2xl border border-[#E7DFD3] shadow-md p-6 space-y-4">
            <div className="flex items-center gap-3 text-[#A86236]">
              <div className="w-10 h-10 rounded-xl bg-[#FDF1EB] border border-[#F3CEBD] flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-[#A86236]" />
              </div>
              <div>
                <h2 className="text-base font-bold font-sans">TERRANODE UI Recovered</h2>
                <p className="text-xs text-[#7D7063] font-mono">Render exception intercepted</p>
              </div>
            </div>

            <div className="p-3 bg-[#FAF8F3] rounded-xl border border-[#E7DFD3] font-mono text-xs text-[#8F4F28] overflow-auto max-h-40">
              {this.state.error?.message || 'Unknown runtime error'}
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => window.location.reload()}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-xl bg-[#A86236] text-white font-semibold text-xs hover:bg-[#8F4F28] transition cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reload Page</span>
              </button>
              <button
                onClick={this.handleReset}
                className="flex items-center justify-center py-2 px-4 rounded-xl border border-[#E7DFD3] bg-white text-[#7D7063] hover:bg-[#FAF8F3] font-semibold text-xs transition cursor-pointer"
              >
                Reset Session
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
