'use client';

import { Suspense } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import the AgentValley component to avoid SSR issues with PixiJS
const AgentValleyApp = dynamic(
  () => import('@/features/agent-valley/components/AgentValleyApp'),
  { ssr: false }
);

export default function AgentValleyPage() {
  return (
    <div className="h-screen w-screen overflow-hidden bg-black">
      <Suspense fallback={
        <div className="flex h-full w-full items-center justify-center text-white">
          <div className="text-center">
            <div className="mb-4 text-2xl font-bold">Loading Agent Valley...</div>
            <div className="text-sm opacity-70">Initializing visualization engine</div>
          </div>
        </div>
      }>
        <AgentValleyApp />
      </Suspense>
    </div>
  );
}
