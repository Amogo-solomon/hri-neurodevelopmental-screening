import type { Metadata } from 'next';
import './globals.css';
import { QueryProvider } from '@/components/layout/QueryProvider';
import { ThemeProvider } from '@/components/layout/ThemeProvider';
import { AuthGuard }    from '@/components/auth/AuthGuard';

export const metadata: Metadata = {
  title: 'HRI Behaviour Analysis Platform | University of Lincoln',
  description:
    'Explainable Behaviour Analysis in Human-Robot Interaction. ' +
    'Research platform for neurodivergence screening support. Not for clinical use.',
  keywords: ['HRI', 'VLM', 'AQ-10', 'ADOS', 'explainable AI', 'child-robot interaction'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-slate-950 text-slate-100 antialiased font-sans">
        <ThemeProvider>
          <QueryProvider>
            <AuthGuard>{children}</AuthGuard>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}