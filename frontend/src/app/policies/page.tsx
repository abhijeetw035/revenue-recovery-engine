export default async function Policies() {
  let data = null;
  let error = null;

  try {
    const res = await fetch('http://127.0.0.1:8000/api/policies/', { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch policies');
    const json = await res.json();
    data = json.data;
  } catch (err: any) {
    error = err.message;
  }

  if (error) return <div className="error">Error loading Policies: {error}</div>;
  if (!data) return <div className="loading">Loading...</div>;

  // Group by segment
  const bySegment: Record<string, any[]> = {};
  data.forEach((p: any) => {
    if (!bySegment[p.segment]) bySegment[p.segment] = [];
    bySegment[p.segment].push(p);
  });

  return (
    <div>
      <h2>Policy Engine</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Active policies and their version history across all segments.
      </p>

      {Object.keys(bySegment).length === 0 ? (
        <p>No policies have been generated yet.</p>
      ) : (
        Object.entries(bySegment).map(([segment, policies]) => {
          const activePolicy = policies[0]; // Assuming ordered by -version from API
          
          return (
            <div key={segment} className="table-container" style={{ marginBottom: '3rem' }}>
              <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0, marginBottom: '0.5rem' }}>{segment}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Active Action:</span>
                    <span className="badge success">{activePolicy.action}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginLeft: '1rem' }}>v{activePolicy.version}</span>
                  </div>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '10%' }}>Version</th>
                    <th style={{ width: '20%' }}>Action</th>
                    <th style={{ width: '40%' }}>Reason</th>
                    <th style={{ width: '30%' }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((p: any) => (
                    <tr key={p.id}>
                      <td>v{p.version}</td>
                      <td style={{ fontWeight: 600 }}>{p.action}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{p.reason}</td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{new Date(p.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })
      )}
    </div>
  );
}
