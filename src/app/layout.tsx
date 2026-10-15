import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'AI Career Launchpad', description: 'Build your next career move with clarity.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
