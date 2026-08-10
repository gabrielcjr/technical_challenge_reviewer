import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import Home from './Home';

// Mock the global fetch
window.fetch = vi.fn();

describe('Home Page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  const renderWithRouter = (component: React.ReactElement) => {
    return render(<BrowserRouter>{component}</BrowserRouter>);
  };

  it('shows loading state initially', () => {
    (window.fetch as any).mockImplementation(() => new Promise(() => {}));
    
    renderWithRouter(<Home />);
    
    // It should just have the loading spinner (no headings)
    expect(screen.queryByText('Challenges')).not.toBeInTheDocument();
  });

  it('renders challenges and submissions after fetch', async () => {
    const mockChallenges = [
      { id: '1', title: 'Test Challenge', description: 'Desc', createdAt: new Date().toISOString() }
    ];
    
    const mockSubmissions = [
      { 
        id: '1', 
        userName: 'John Doe', 
        githubRepoUrl: 'https://github.com/test', 
        status: 'approved', 
        approved: true,
        createdAt: new Date().toISOString()
      }
    ];

    (window.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/challenges') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockChallenges)
        });
      }
      if (url === '/api/submissions') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSubmissions)
        });
      }
      return Promise.reject(new Error('not found'));
    });

    renderWithRouter(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Test Challenge')).toBeInTheDocument();
    });

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('https://github.com/test')).toBeInTheDocument();
    expect(screen.getByText('approved')).toBeInTheDocument();
  });
});
