export default async function Experiments() {
  let data = null;
  let error = null;
  
  try {
    const res = await fetch('http://127.0.0.1:8000/api/experiments/', { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch experiments');
    const json = await res.json();
    data = json.data;
  } catch (err: any) {
    error = err.message;
  }

  if (error) return <div className="error">Error loading Experiments: {error}</div>;
  if (!data) return <div className="loading">Loading...</div>;

  return (
    <div>
      <h2>Experiment Results</h2>
      
      {data.length === 0 ? (
        <p>No experiments found.</p>
      ) : (
        data.map((exp: any) => (
          <div key={exp.id} className="table-container" style={{ marginBottom: '3rem' }}>
            <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border)', backgroundColor: 'rgba(0,0,0,0.2)' }}>
              <h3>Segment: {exp.target_segment}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                ID: {exp.id} | Status: <span className={`badge ${exp.status === 'COMPLETED' ? 'success' : 'neutral'}`}>{exp.status}</span>
              </p>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Treatment Arm</th>
                  <th>Sample Size (C / T)</th>
                  <th>Rates (C / T)</th>
                  <th>Absolute Lift</th>
                  <th>95% CI</th>
                  <th>Evidence Status</th>
                </tr>
              </thead>
              <tbody>
                {exp.results.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center' }}>No results calculated yet.</td>
                  </tr>
                ) : (
                  exp.results.map((res: any, i: number) => {
                    const lift = res.lift * 100;
                    const c_rate = res.control_rate * 100;
                    const t_rate = res.treatment_rate * 100;
                    const ci_lower = res.ci_lower * 100;
                    const ci_upper = res.ci_upper * 100;
                    
                    let badgeClass = 'neutral';
                    if (res.evidence_status === 'POSITIVE') badgeClass = 'success';
                    if (res.evidence_status === 'NEGATIVE') badgeClass = 'danger';
                    if (res.evidence_status === 'INSUFFICIENT_SAMPLE') badgeClass = 'warning';
                    
                    return (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{res.treatment}</td>
                        <td>{res.control_n} / {res.treatment_n}</td>
                        <td>{c_rate.toFixed(1)}% / {t_rate.toFixed(1)}%</td>
                        <td style={{ color: lift > 0 ? 'var(--success)' : lift < 0 ? 'var(--danger)' : 'inherit' }}>
                          {lift > 0 ? '+' : ''}{lift.toFixed(2)}%
                        </td>
                        <td style={{ color: 'var(--text-muted)' }}>
                          [{ci_lower.toFixed(2)}%, {ci_upper.toFixed(2)}%]
                        </td>
                        <td>
                          <span className={`badge ${badgeClass}`}>{res.evidence_status}</span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        ))
      )}
    </div>
  );
}
