import './globals.css';
import Link from 'next/link';
import { ReactNode } from 'react';

export const metadata = {
  title: 'Revenue Optimizer',
  description: 'Automated Recovery Strategy System',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-container">
          <nav className="sidebar">
            <h1>Revenue Optimizer</h1>
            <Link href="/" className="nav-link">Revenue Overview</Link>
            <Link href="/experiments" className="nav-link">Experiments</Link>
            <Link href="/policies" className="nav-link">Policies</Link>
            <Link href="/impact" className="nav-link">Impact</Link>
            <Link href="/audit" className="nav-link">Audit Log</Link>
          </nav>
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
