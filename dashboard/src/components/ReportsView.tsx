import { useState, useEffect } from 'react';
import { listReports, createDeepResearch } from '../api';

interface Report {
  path: string;
  filename: string;
  timestamp: string;
  total_companies: number;
  has_deep_research: boolean;
  providers: string[];
  report_type?: 'discovery' | 'deep_research';
}

export function ReportsView() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [topN, setTopN] = useState(25);
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    loadReports();
  }, []);

  async function loadReports() {
    try {
      setLoading(true);
      const data = await listReports();
      setReports(data.reports);
    } catch (error) {
      console.error('Failed to load reports:', error);
    } finally {
      setLoading(false);
    }
  }

  async function launchDeepResearch() {
    if (!selectedReport) return;

    try {
      setLaunching(true);
      const result = await createDeepResearch({
        report_path: selectedReport.path,
        top_n: topN,
        config_path: 'config/dev.yaml',
      });

      alert(`Deep research launched! Run ID: ${result.run.run_id}`);
      
      // Navigate to runs view (you could use router here)
      window.location.href = '/';
    } catch (error) {
      console.error('Failed to launch deep research:', error);
      alert('Failed to launch deep research. See console for details.');
    } finally {
      setLaunching(false);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <p>Loading reports...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '2rem',
      }}>
        <h1 style={{ margin: 0 }}>Discovery Reports</h1>
        <button onClick={loadReports} style={{ padding: '0.5rem 1rem' }}>
          Refresh
        </button>
      </div>

      {reports.length === 0 ? (
        <p>No reports found. Run a discovery first.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {reports.map((report) => (
            <div
              key={report.path}
              style={{
                border: selectedReport?.path === report.path ? '2px solid #4CAF50' : '1px solid #ddd',
                borderRadius: '8px',
                padding: '1.5rem',
                backgroundColor: selectedReport?.path === report.path ? '#f0f9f0' : 'white',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onClick={() => setSelectedReport(report)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div>
                  <h3 style={{ margin: '0 0 0.5rem 0' }}>
                    {report.filename}
                  </h3>
                  <p style={{ margin: '0.25rem 0', color: '#666', fontSize: '0.9rem' }}>
                    {new Date(report.timestamp).toLocaleString()}
                  </p>
                  <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem' }}>
                    <span style={{ 
                      padding: '0.25rem 0.75rem', 
                      background: '#e3f2fd', 
                      borderRadius: '4px',
                      fontSize: '0.85rem',
                    }}>
                      {report.total_companies} companies
                    </span>
                    {report.report_type === 'deep_research' ? (
                      <span style={{ 
                        padding: '0.25rem 0.75rem', 
                        background: '#e8f5e9', 
                        borderRadius: '4px',
                        fontSize: '0.85rem',
                        fontWeight: 'bold',
                        color: '#2e7d32',
                      }}>
                        🔬 Deep Research Report
                      </span>
                    ) : (
                      <>
                        <span style={{ 
                          padding: '0.25rem 0.75rem', 
                          background: '#f3e5f5', 
                          borderRadius: '4px',
                          fontSize: '0.85rem',
                        }}>
                          {report.providers.join(', ')}
                        </span>
                        {report.has_deep_research && (
                          <span style={{ 
                            padding: '0.25rem 0.75rem', 
                            background: '#e8f5e9', 
                            borderRadius: '4px',
                            fontSize: '0.85rem',
                            fontWeight: 'bold',
                          }}>
                            ✓ With Deep Research
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>
                {selectedReport?.path === report.path && (
                  <div style={{ 
                    width: '24px', 
                    height: '24px', 
                    borderRadius: '50%',
                    background: '#4CAF50',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1rem',
                  }}>
                    ✓
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedReport && (
        <div style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'white',
          borderTop: '2px solid #4CAF50',
          padding: '1.5rem',
          boxShadow: '0 -2px 10px rgba(0,0,0,0.1)',
        }}>
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            <h3 style={{ margin: '0 0 1rem 0' }}>
              Launch Deep Research
            </h3>
            <p style={{ margin: '0 0 1rem 0', color: '#666' }}>
              Selected: <strong>{selectedReport.filename}</strong>
            </p>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                Top N companies:
                <input
                  type="number"
                  value={topN}
                  onChange={(e) => setTopN(Math.max(1, parseInt(e.target.value) || 1))}
                  min="1"
                  max="100"
                  style={{
                    padding: '0.5rem',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    width: '80px',
                  }}
                />
              </label>
              <button
                onClick={launchDeepResearch}
                disabled={launching}
                style={{
                  padding: '0.75rem 2rem',
                  background: launching ? '#ccc' : '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: launching ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                }}
              >
                {launching ? 'Launching...' : 'Launch Deep Research'}
              </button>
              <button
                onClick={() => setSelectedReport(null)}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#f5f5f5',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
            <p style={{ margin: '1rem 0 0 0', fontSize: '0.85rem', color: '#666' }}>
              Cost estimate: ~${(topN * 0.01).toFixed(2)} ($0.01/company - Perplexity + GPT-4o)
              <br />
              Time estimate: ~{Math.ceil(topN / 5 * 7)} minutes ({topN} companies, 5 concurrent)
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

