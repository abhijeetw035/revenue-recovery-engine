export default async function RevenueOverview() {
  let data = null;
  let error = null;
  try {
    const res = await fetch('http://127.0.0.1:8000/api/summary/', { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch summary data');
    const json = await res.json();
    data = json.data;
  } catch (err: any) {
    error = err.message;
  }

  if (error) {
    return <div className="error">Error loading Revenue Overview: {error}</div>;
  }

  if (!data) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div>
      <h2>Revenue Overview</h2>
      
      <div className="card-grid">
        <div className="card">
          <div className="card-title">Total Transactions</div>
          <div className="card-value">{data.transaction_count.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-title">Revenue at Risk</div>
          <div className="card-value">${data.revenue_at_risk.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        <div>
          <h3>By Failure Reason</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>Count</th>
                  <th>At Risk ($)</th>
                </tr>
              </thead>
              <tbody>
                {data.by_reason.map((item: any, i: number) => (
                  <tr key={i}>
                    <td>{item.failure_reason}</td>
                    <td>{item.count.toLocaleString()}</td>
                    <td>${item.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3>By Segment</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Segment</th>
                  <th>Count</th>
                  <th>At Risk ($)</th>
                </tr>
              </thead>
              <tbody>
                {data.by_segment.map((item: any, i: number) => (
                  <tr key={i}>
                    <td>{item.segment}</td>
                    <td>{item.count.toLocaleString()}</td>
                    <td>${item.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
