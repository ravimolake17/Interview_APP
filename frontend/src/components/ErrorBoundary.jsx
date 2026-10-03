import { Component } from 'react';
import DualCompanyLogos from './DualCompanyLogos';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('RR Parkon UI crashed', error, info);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div
        className="min-h-screen flex items-center justify-center p-6"
        style={{ background: 'var(--color-bg)' }}
      >
        <div className="w-full max-w-md text-center space-y-4">
          <DualCompanyLogos height={48} className="mx-auto" />
          <h1 className="text-lg font-semibold text-col">Unable to load this page</h1>
          <p className="text-sm text-muted">
            Please reload. If the problem continues, sign out and sign back in.
          </p>
          <button type="button" className="btn-primary" onClick={this.handleReload}>
            Reload
          </button>
        </div>
      </div>
    );
  }
}
