import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Play, Code } from 'lucide-react';

interface Challenge {
  id: string;
  title: string;
  description: string;
}

export default function NewSubmission() {
  const navigate = useNavigate();
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [userName, setUserName] = useState('');
  const [githubRepoUrl, setGithubRepoUrl] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [customChallengeText, setCustomChallengeText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/challenges')
      .then(res => res.json())
      .then(data => setChallenges(data))
      .catch(err => console.error('Error fetching challenges:', err));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload: any = { userName, githubRepoUrl };
    if (challengeId) {
      payload.challengeId = challengeId;
    } else {
      payload.customChallengeText = customChallengeText;
    }

    try {
      const res = await fetch('/api/submissions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || data.errors ? JSON.stringify(data.errors) : 'Failed to create submission');
      }

      const data = await res.json();
      navigate(`/submissions/${data.id}`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <Link to="/" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Dashboard
        </Link>
      </div>

      <div className="bg-white rounded-2xl shadow-xl shadow-gray-200/50 border border-gray-100 overflow-hidden">
        <div className="p-8 border-b border-gray-100 bg-gradient-to-br from-gray-900 to-gray-800 text-white">
          <div className="flex items-center space-x-3 mb-2">
            <Code className="w-8 h-8" />
            <h1 className="text-3xl font-bold tracking-tight">Submit Code</h1>
          </div>
          <p className="text-gray-300">Queue a GitHub repository for AI evaluation.</p>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {error && (
            <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="userName" className="block text-sm font-medium text-gray-700 mb-1">
                Candidate Name
              </label>
              <input
                type="text"
                id="userName"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                className="w-full rounded-lg border-gray-300 border px-4 py-3 text-gray-900 focus:ring-2 focus:ring-primary focus:border-primary outline-none shadow-sm"
                placeholder="Jane Doe"
                required
              />
            </div>
            <div>
              <label htmlFor="githubRepoUrl" className="block text-sm font-medium text-gray-700 mb-1">
                GitHub Repository URL
              </label>
              <input
                type="url"
                id="githubRepoUrl"
                value={githubRepoUrl}
                onChange={(e) => setGithubRepoUrl(e.target.value)}
                className="w-full rounded-lg border-gray-300 border px-4 py-3 text-gray-900 focus:ring-2 focus:ring-primary focus:border-primary outline-none shadow-sm"
                placeholder="https://github.com/user/repo"
                required
              />
            </div>
          </div>

          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Challenge Definition</h3>
            
            <div className="space-y-4">
              <div className="flex items-center space-x-3">
                <input
                  type="radio"
                  id="useExisting"
                  name="challengeType"
                  checked={challengeId !== ''}
                  onChange={() => { setChallengeId(challenges[0]?.id || ''); setCustomChallengeText(''); }}
                  className="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
                />
                <label htmlFor="useExisting" className="text-sm font-medium text-gray-700">
                  Use existing challenge
                </label>
              </div>
              
              {challengeId !== '' && (
                <div className="ml-7">
                  <select
                    value={challengeId}
                    onChange={(e) => setChallengeId(e.target.value)}
                    className="w-full rounded-lg border-gray-300 border px-4 py-3 text-gray-900 focus:ring-2 focus:ring-primary focus:border-primary outline-none shadow-sm"
                  >
                    {challenges.map(c => (
                      <option key={c.id} value={c.id}>{c.title}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex items-center space-x-3 pt-2">
                <input
                  type="radio"
                  id="useCustom"
                  name="challengeType"
                  checked={challengeId === ''}
                  onChange={() => setChallengeId('')}
                  className="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
                />
                <label htmlFor="useCustom" className="text-sm font-medium text-gray-700">
                  Provide custom instructions
                </label>
              </div>

              {challengeId === '' && (
                <div className="ml-7">
                  <textarea
                    value={customChallengeText}
                    onChange={(e) => setCustomChallengeText(e.target.value)}
                    rows={4}
                    className="w-full rounded-lg border-gray-300 border px-4 py-3 text-gray-900 focus:ring-2 focus:ring-primary focus:border-primary outline-none shadow-sm resize-y"
                    placeholder="Enter instructions for this specific submission..."
                    required
                  />
                </div>
              )}
            </div>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading || !userName || !githubRepoUrl || (challengeId === '' && customChallengeText.length < 20)}
              className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-gray-900 hover:bg-black focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              ) : (
                <>
                  <Play className="w-5 h-5 mr-2" />
                  Start Evaluation
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
