import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Home from './pages/Home';
import NewChallenge from './pages/NewChallenge';
import NewSubmission from './pages/NewSubmission';
import SubmissionDetails from './pages/SubmissionDetails';
import { Rocket, Code } from 'lucide-react';

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col font-sans">
        <header className="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <Link to="/" className="flex items-center space-x-2 group">
                <Rocket className="w-6 h-6 text-primary group-hover:text-primary-focus transition-colors" />
                <span className="font-bold text-xl text-gray-900 tracking-tight">ChallengeReviewer</span>
              </Link>
              <nav className="flex space-x-4">
                <Link to="/challenges/new" className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium transition-colors">
                  New Challenge
                </Link>
                <Link to="/submissions/new" className="bg-gray-900 text-white hover:bg-gray-800 px-4 py-2 rounded-md text-sm font-medium transition-colors shadow-sm flex items-center space-x-2">
                  <Code className="w-4 h-4" />
                  <span>Submit Code</span>
                </Link>
              </nav>
            </div>
          </div>
        </header>

        <main className="flex-grow max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/challenges/new" element={<NewChallenge />} />
            <Route path="/submissions/new" element={<NewSubmission />} />
            <Route path="/submissions/:id" element={<SubmissionDetails />} />
          </Routes>
        </main>
        
        <footer className="bg-white border-t border-gray-200 py-8 mt-auto">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-gray-500 text-sm">
            <p>Powered by Vite, React, and Tailwind CSS v4</p>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
