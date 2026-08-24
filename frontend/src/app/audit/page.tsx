export default async function Audit() {
  let data = null;
  let error = null;

  try {
    const res = await fetch('http://127.0.0.1:8000/api/audit/', { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch audit log');
    const json = await res.json();
    data = json.data;
  } catch (err: any) {
    error = err.message;
  }

  if (error) return <div className="error">Error loading Audit Log: {error}</div>;
  if (!data) return <div className="loading">Loading...</div>;

  return (
    <div>
      <h2>Transaction Audit Log</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Sample of recent transactions showing allocator decisions and safety constraints.
      </p>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Transaction ID</th>
              <th>Segment</th>
              <th>Amount</th>
              <th>Allocated Action</th>
              <th>Expected Net Value</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.map((tx: any) => {
              let badgeClass = 'neutral';
              if (tx.status === 'RECOVERED') badgeClass = 'success';
              if (tx.status === 'STOPPED') badgeClass = 'danger';
              if (tx.status === 'HUMAN_REVIEW') badgeClass = 'warning';
              
              return (
                <tr key={tx.id}>
                  <td style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>{tx.id.split('-')[0]}...</td>
                  <td style={{ fontSize: '0.75rem' }}>{tx.segment}</td>
                  <td>${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  <td style={{ fontWeight: 600 }}>{tx.action}</td>
                  <td style={{ color: tx.expected_net_value > 0 ? 'var(--success)' : tx.expected_net_value < 0 ? 'var(--danger)' : 'inherit' }}>
                    ${tx.expected_net_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td>
                    <span className={`badge ${badgeClass}`}>{tx.status}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
