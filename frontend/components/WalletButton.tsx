"use client";

import { useAccount, useConnect, useDisconnect } from "wagmi";
import { metaMask } from "wagmi/connectors";
import { Wallet, LogOut, ChevronDown } from "lucide-react";
import { useState } from "react";
import { cn, truncateHash } from "@/lib/utils";

export default function WalletButton() {
  const { address, isConnected } = useAccount();
  const { connect, isPending } = useConnect();
  const { disconnect } = useDisconnect();
  const [menuOpen, setMenuOpen] = useState(false);

  if (!isConnected) {
    return (
      <button
        onClick={() => connect({ connector: metaMask() })}
        disabled={isPending}
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all",
          "bg-accent hover:bg-accent-hover text-white",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
      >
        <Wallet className="w-4 h-4" />
        {isPending ? "Connecting..." : "Connect Wallet"}
      </button>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setMenuOpen((o) => !o)}
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all",
          "bg-surface-raised border border-border hover:border-accent text-white"
        )}
      >
        <span className="w-2 h-2 rounded-full bg-success" />
        {truncateHash(address ?? "", 12)}
        <ChevronDown className="w-3 h-3 text-muted" />
      </button>

      {menuOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute right-0 top-12 z-20 w-48 bg-surface-raised border border-border rounded-xl shadow-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <p className="text-xs text-muted">Connected</p>
              <p className="text-sm text-white font-mono mt-0.5 truncate">
                {address}
              </p>
            </div>
            <button
              onClick={() => {
                disconnect();
                setMenuOpen(false);
              }}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm text-error hover:bg-surface transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Disconnect
            </button>
          </div>
        </>
      )}
    </div>
  );
}
