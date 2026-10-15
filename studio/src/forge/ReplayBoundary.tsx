import { Component, type ReactNode } from 'react'

/** A replay payload from the server that the viewer cannot draw becomes a visible message, not a blank page. */
export class ReplayBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: string | null; key?: string }> {
  state: { error: string | null; key?: string } = { error: null }
  static getDerivedStateFromError(e: Error) {
    return { error: e.message }
  }
  static getDerivedStateFromProps(p: { resetKey?: string }, s: { error: string | null; key?: string }) {
    return p.resetKey !== s.key ? { error: null, key: p.resetKey } : null
  }
  render() {
    if (this.state.error) {
      return <div className="error" role="alert" data-testid="replay-draw-error">The replay came back in a shape the viewer cannot draw: {this.state.error}</div>
    }
    return this.props.children
  }
}
