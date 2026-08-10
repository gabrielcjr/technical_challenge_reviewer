import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Mock the components so we just test the App layout and routing skeleton
vi.mock('./pages/Home', () => ({
  default: () => <div data-testid="home-page">Home Page</div>
}));
vi.mock('./pages/NewChallenge', () => ({
  default: () => <div data-testid="new-challenge-page">New Challenge</div>
}));
vi.mock('./pages/NewSubmission', () => ({
  default: () => <div data-testid="new-submission-page">New Submission</div>
}));
vi.mock('./pages/SubmissionDetails', () => ({
  default: () => <div data-testid="submission-details-page">Submission Details</div>
}));

describe('App Layout', () => {
  it('renders the header with the correct links', () => {
    render(<App />);
    expect(screen.getByText('ChallengeReviewer')).toBeInTheDocument();
    expect(screen.getByText('New Challenge')).toBeInTheDocument();
    expect(screen.getByText('Submit Code')).toBeInTheDocument();
  });

  it('renders the footer', () => {
    render(<App />);
    expect(screen.getByText(/Powered by Vite/)).toBeInTheDocument();
  });
});
