import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { CheckCircle, XCircle, Clock, AlertTriangle, ChevronRight } from 'lucide-react';

interface Challenge {
  id: string;
  title: string;
  description: string;
  createdAt: string;
}

interface Submission {
  id: string;
  userName: string;
  githubRepoUrl: string;
  challengeId?: string;
  challengeSnapshot: string;
  status: string;
  approved: boolean;
  createdAt: string;
}

export default function Home() {
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [challengesRes, submissionsRes] = await Promise.all([
          fetch('/api/challenges'),
          fetch('/api/submissions')
        ]);
        
        if (challengesRes.ok) setChallenges(await challengesRes.json());
        if (submissionsRes.ok) setSubmissions(await submissionsRes.json());
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved': return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'rejected': return <XCircle className="w-5 h-5 text-red-500" />;
      case 'failed': return <AlertTriangle className="w-5 h-5 text-amber-500" />;
      default: return <Clock className="w-5 h-5 text-blue-500 animate-pulse" />;
    }
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'approved': return 'bg-green-50 text-green-700 ring-green-600/20';
      case 'rejected': return 'bg-red-50 text-red-700 ring-red-600/10';
      case 'failed': return 'bg-amber-50 text-amber-800 ring-amber-600/20';
      default: return 'bg-blue-50 text-blue-700 ring-blue-700/10';
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Left Column: Challenges */}
      <div className="lg:col-span-1 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Challenges</h2>
          <Link to="/challenges/new" className="text-sm text-primary hover:text-primary-focus font-medium transition-colors">
            + New
          </Link>
        </div>
        
        <div className="space-y-4">
          {challenges.length === 0 ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 text-center text-gray-500">
              No challenges created yet.
            </div>
          ) : (
            challenges.map(challenge => (
              <div key={challenge.id} className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-gray-100 p-5 group cursor-pointer">
                <h3 className="font-semibold text-gray-900 group-hover:text-primary transition-colors">{challenge.title}</h3>
                <p className="text-sm text-gray-500 mt-2 line-clamp-2">{challenge.description}</p>
                <div className="mt-4 text-xs text-gray-400">
                  {formatDistanceToNow(new Date(challenge.createdAt), { addSuffix: true })}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Column: Submissions */}
      <div className="lg:col-span-2 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Recent Submissions</h2>
          <Link to="/submissions/new" className="text-sm text-primary hover:text-primary-focus font-medium transition-colors">
            + Submit Code
          </Link>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <ul className="divide-y divide-gray-100">
            {submissions.length === 0 ? (
              <li className="p-8 text-center text-gray-500">No submissions yet.</li>
            ) : (
              submissions.map(submission => (
                <li key={submission.id} className="hover:bg-gray-50/50 transition-colors">
                  <Link to={`/submissions/${submission.id}`} className="block p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        {getStatusIcon(submission.status)}
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {submission.userName}
                          </p>
                          <p className="text-sm text-gray-500 truncate max-w-xs md:max-w-md">
                            {submission.githubRepoUrl}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${getStatusStyle(submission.status)} uppercase tracking-wider`}>
                          {submission.status}
                        </span>
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      </div>
                    </div>
                  </Link>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
