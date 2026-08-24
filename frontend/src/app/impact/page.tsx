export default async function Impact() {
  let data = null;
  let error = null;

  try {
    const res = await fetch('http://127.0.0.1:8000/api/impact/', { cache: 'no-store' });
    const json = await res.json();
    if (json.status === 'error') {
      error = json.message;
    } else {
      data = json.data;
    }
  } catch (err: any) {
    error = err.message;
  }

  if (error) return <div className="error">Error loading Impact Data: {error}</div>;
  if (!data) return <div className="loading">Loading...</div>;

  const strategies = ['Naive', 'Static', 'Learned'];
  
  // Find max values for chart scaling
  const maxNetRecovery = Math.max(...strategies.map(s => data[s].net_recovery));
  const maxCost = Math.max(...strategies.map(s => data[s].intervention_cost));

  return (
    <div>
      <h2>Business Impact Evaluation</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Comparing recovery strategies on a simulated 10k transaction portfolio.
      </p>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Recovery Rate</th>
              <th>Gross Recovery</th>
              <th>Total Cost</th>
              <th>Net Recovery</th>
              <th>Incremental (vs Naive)</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map(s => {
              const metrics = data[s];
              const rate = (metrics.recovery_rate * 100).toFixed(2);
              const gross = metrics.gross_recovery.toLocaleString(undefined, { minimumFractionDigits: 2 });
              const cost = metrics.intervention_cost.toLocaleString(undefined, { minimumFractionDigits: 2 });
              const net = metrics.net_recovery.toLocaleString(undefined, { minimumFractionDigits: 2 });
              const incr = metrics.incremental_recovery_vs_naive.toLocaleString(undefined, { minimumFractionDigits: 2 });
              const incrNum = metrics.incremental_recovery_vs_naive;
              
              return (
                <tr key={s}>
                  <td style={{ fontWeight: 600 }}>{s}</td>
                  <td>{rate}%</td>
                  <td>${gross}</td>
                  <td>${cost}</td>
                  <td style={{ fontWeight: 600 }}>${net}</td>
                  <td style={{ color: incrNum > 0 ? 'var(--success)' : incrNum < 0 ? 'var(--danger)' : 'inherit' }}>
                    {incrNum > 0 ? '+' : ''}${incr}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        <div className="card">
          <h3>Net Recovery Comparison</h3>
          {strategies.map(s => {
            const net = data[s].net_recovery;
            const percentage = Math.max(0, (net / maxNetRecovery) * 100);
            return (
              <div key={s} style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                  <span>{s}</span>
                  <span>${net.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </div>
                <div className="bar-container">
                  <div className="bar-fill" style={{ width: `${percentage}%`, backgroundColor: 'var(--success)' }}></div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="card">
          <h3>Intervention Cost</h3>
          {strategies.map(s => {
            const cost = data[s].intervention_cost;
            const percentage = maxCost > 0 ? (cost / maxCost) * 100 : 0;
            return (
              <div key={s} style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                  <span>{s}</span>
                  <span>${cost.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </div>
                <div className="bar-container">
                  <div className="bar-fill" style={{ width: `${percentage}%`, backgroundColor: 'var(--danger)' }}></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
