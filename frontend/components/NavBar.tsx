"use client";

import React from "react";
import Link from "next/link";

export default function NavBar() {
  return (
    <nav className="w-full h-20 border-b border-neutral-100 flex items-center justify-between px-12 bg-white sticky top-0 z-50">
      <Link href="/" className="flex items-center gap-2.5 font-mono text-xl font-bold tracking-tighter">
        <span className="relative flex h-2.5 w-2.5">
          <span className="tv-pulse-dot absolute inline-flex h-full w-full rounded-full bg-[#76b900] opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#76b900]" />
        </span>
        <span className="text-[#76b900]">GAS</span><span className="text-neutral-900">LIT</span>
      </Link>

      <div className="hidden md:flex gap-8 text-[11px] uppercase tracking-widest font-bold text-neutral-500">
        <Link href="/" className="hover:text-[#76b900] transition-colors">Home</Link>
        <Link href="/about" className="hover:text-[#76b900] transition-colors">About</Link>
        <Link href="/console" className="hover:text-[#76b900] transition-colors">Console</Link>
        <Link href="https://arxiv.org/abs/2503.03704" target="_blank" rel="noopener noreferrer" className="hover:text-[#76b900] transition-colors">MINJA Paper</Link>
      </div>

      <div className="hidden md:flex items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-[10px] font-mono font-medium text-neutral-500 uppercase tracking-widest">
        <span className="relative flex h-1.5 w-1.5">
          <span className="tv-pulse-dot absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
        </span>
        pipeline online
      </div>
    </nav>
  );
}
