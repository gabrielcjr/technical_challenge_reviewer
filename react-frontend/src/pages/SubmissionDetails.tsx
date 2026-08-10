import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle, XCircle, Clock, AlertTriangle, RefreshCw, Code } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface Submission {
  id: string;
  userName: string;
  githubRepoUrl: string;
  challengeSnapshot: string;
  status: string;
  approved: boolean;
  evaluation: any;
  processingLogs: string;
  createdAt: string;
}

export default function SubmissionDetails() {
  const { id } = useParams<{ id: string }>();
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);

  const fetchSubmission = async () => {
    try {
      const res = await fetch(`/api/submissions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSubmission(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubmission();
    
    // Poll every 3 seconds if pending or processing
    const interval = setInterval(() => {
      if (submission && (submission.status === 'pending' || submission.status === 'processing')) {
        fetchSubmission();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [id, submission?.status]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await fetch(`/api/submissions/${id}/retry`, { method: 'POST' });
      await fetchSubmission();
    } catch (err) {
      console.error(err);
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!submission) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900">Submission not found</h2>
        <Link to="/" className="text-primary hover:underline mt-4 inline-block">Back to Home</Link>
      </div>
    );
  }

  const isFinal = ['approved', 'rejected'].includes(submission.status);
  const isFailed = submission.status === 'failed';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link to="/" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Dashboard
        </Link>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {/* Header */}
        <div className="p-8 border-b border-gray-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center space-x-2">
              <span>{submission.userName}</span>
            </h1>
            <a href={submission.githubRepoUrl} target="_blank" rel="noopener noreferrer" className="flex items-center text-gray-500 hover:text-gray-900 mt-2 text-sm transition-colors">
              <Code className="w-4 h-4 mr-1" />
              {submission.githubRepoUrl}
            </a>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-400">
              {formatDistanceToNow(new Date(submission.createdAt), { addSuffix: true })}
            </span>
            <div className={`px-4 py-2 rounded-full text-sm font-bold uppercase tracking-wider flex items-center space-x-2
              ${submission.status === 'approved' ? 'bg-green-100 text-green-800' : ''}
              ${submission.status === 'rejected' ? 'bg-red-100 text-red-800' : ''}
              ${submission.status === 'failed' ? 'bg-amber-100 text-amber-800' : ''}
              ${!isFinal && !isFailed ? 'bg-blue-100 text-blue-800' : ''}
            `}>
              {submission.status === 'approved' && <CheckCircle className="w-4 h-4" />}
              {submission.status === 'rejected' && <XCircle className="w-4 h-4" />}
              {submission.status === 'failed' && <AlertTriangle className="w-4 h-4" />}
              {!isFinal && !isFailed && <Clock className="w-4 h-4 animate-pulse" />}
              <span>{submission.status}</span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-8 space-y-8 bg-gray-50/50">
          
          {/* Active Processing State */}
          {!isFinal && !isFailed && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-6 flex items-center space-x-4">
              <RefreshCw className="w-6 h-6 text-blue-500 animate-spin" />
              <div>
                <h3 className="text-blue-900 font-medium">Evaluation in progress</h3>
                <p className="text-blue-700 text-sm mt-1">The AI is cloning the repository and analyzing the code. This usually takes 1-2 minutes.</p>
              </div>
            </div>
          )}

          {/* Failed State */}
          {isFailed && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  <AlertTriangle className="w-6 h-6 text-amber-500 mt-0.5" />
                  <div>
                    <h3 className="text-amber-900 font-medium">Evaluation Failed</h3>
                    <p className="text-amber-700 text-sm mt-1">There was a system or infrastructure error (e.g. invalid repo, timeout). You can retry the evaluation.</p>
                  </div>
                </div>
                <button
                  onClick={handleRetry}
                  disabled={retrying}
                  className="flex items-center space-x-2 bg-white text-amber-700 border border-amber-200 hover:bg-amber-100 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 ${retrying ? 'animate-spin' : ''}`} />
                  <span>Retry</span>
                </button>
              </div>
            </div>
          )}

          {/* Evaluation Result */}
          {submission.evaluation && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-gray-900 border-b border-gray-200 pb-2">AI Evaluation Report</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2 space-y-6">
                  {/* Feedback */}
                  <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                    <h3 className="font-semibold text-gray-900 mb-3">Overall Feedback</h3>
                    <div className="prose prose-sm text-gray-700 max-w-none">
                      {submission.evaluation.summary}
                    </div>
                  </div>

                  {/* Reasoning */}
                  {submission.evaluation.reasoning && (
                    <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                      <h3 className="font-semibold text-gray-900 mb-3">Detailed Reasoning</h3>
                      <div className="prose prose-sm text-gray-700 max-w-none">
                        {submission.evaluation.reasoning}
                      </div>
                    </div>
                  )}
                  
                  {/* Improvements */}
                  {submission.evaluation.improvements && submission.evaluation.improvements.length > 0 && (
                    <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                      <h3 className="font-semibold text-gray-900 mb-3">Suggested Improvements</h3>
                      <ul className="list-disc pl-5 space-y-2 text-gray-700 text-sm">
                        {submission.evaluation.improvements.map((imp: string, idx: number) => (
                          <li key={idx}>{imp}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="space-y-6">
                  {/* Verdict */}
                  <div className={`p-6 rounded-xl border flex flex-col items-center justify-center space-y-4 ${submission.approved ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                    <h3 className={`text-lg font-bold uppercase tracking-wider text-center ${submission.approved ? 'text-green-800' : 'text-red-800'}`}>
                      {submission.approved ? 'Candidate Approved' : 'Candidate Rejected'}
                    </h3>
                  </div>
                  
                  {/* Strengths & Weaknesses */}
                  {submission.evaluation.strengths && submission.evaluation.strengths.length > 0 && (
                    <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
                      <h3 className="text-sm font-semibold text-gray-900 mb-3">Strengths</h3>
                      <ul className="space-y-2">
                        {submission.evaluation.strengths.map((str: string, idx: number) => (
                          <li key={idx} className="flex items-start space-x-2 text-sm text-gray-600">
                            <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                            <span>{str}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {submission.evaluation.weaknesses && submission.evaluation.weaknesses.length > 0 && (
                    <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
                      <h3 className="text-sm font-semibold text-gray-900 mb-3">Weaknesses</h3>
                      <ul className="space-y-2">
                        {submission.evaluation.weaknesses.map((weak: string, idx: number) => (
                          <li key={idx} className="flex items-start space-x-2 text-sm text-gray-600">
                            <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                            <span>{weak}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Challenge Snapshot */}
          <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Challenge Instructions Evaluated Against</h3>
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600 whitespace-pre-wrap font-mono">
              {submission.challengeSnapshot}
            </div>
          </div>

          {/* Logs */}
          {submission.processingLogs && (
            <div className="bg-gray-900 rounded-xl overflow-hidden shadow-sm">
              <div className="px-4 py-2 border-b border-gray-800 bg-gray-900 flex justify-between items-center">
                <span className="text-xs font-mono text-gray-400">System Logs</span>
              </div>
              <div className="p-4 text-xs font-mono text-gray-300 whitespace-pre-wrap overflow-x-auto">
                {submission.processingLogs}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
