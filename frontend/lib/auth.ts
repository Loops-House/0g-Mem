"use client";

/**
 * auth.ts — MetaMask signature-based authentication helpers.
 * The user's private key NEVER leaves the browser. We only use `signMessage`
 * to produce a signature that proves wallet ownership.
 */

import { signMessage } from "wagmi/actions";
import { wagmiConfig } from "./wagmi";

export interface AuthHeaders {
  "X-Wallet-Address": string;
  "X-Signature": string;
  "X-Auth-Message": string;
}

/**
 * Build the canonical authentication message that the user will sign.
 * Including the timestamp prevents replay attacks within a session.
 */
export function buildAuthMessage(walletAddress: string): string {
  const timestamp = Date.now();
  return `0g Mem authentication | Wallet: ${walletAddress} | Timestamp: ${timestamp}`;
}

/**
 * Sign the auth message with MetaMask and return the three headers needed
 * by every authenticated API call.
 */
export async function getAuthHeaders(walletAddress: string): Promise<AuthHeaders> {
  const message = buildAuthMessage(walletAddress);
  const signature = await signMessage(wagmiConfig, { message });
  return {
    "X-Wallet-Address": walletAddress,
    "X-Signature": signature,
    "X-Auth-Message": message,
  };
}
