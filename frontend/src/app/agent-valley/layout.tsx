import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Agent Valley',
  description: 'Agent visualization',
};

export default function AgentValleyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
