import { useCallback, useEffect, useState } from 'react';

const DASHBOARD_URL = (() => {
  const base =
    import.meta.env.VITE_BOT_START_URL || 'http://localhost:7860/start';
  return base.replace(/\/start\/?$/, '') + '/api/wallet-dashboard';
})();

interface Holding {
  symbol: string;
  amount: number;
  price_usd: number;
  value_usd: number;
}

interface WalletDashboard {
  address: string | null;
  network: string;
  faucet_url: string | null;
  instructions: string | null;
  error: string | null;
  holdings: Holding[];
  total_usd: number;
}

function qrImageUrl(address: string, size = 160): string {
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(address)}`;
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatAmount(amount: number, symbol: string): string {
  const isStable = ['USDC', 'USDT', 'USDB'].includes(symbol.toUpperCase());
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: isStable ? 2 : 6,
  }).format(amount);
}

export function WalletPanel() {
  const [data, setData] = useState<WalletDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(DASHBOARD_URL);
      const json = await res.json();
      setData({
        address: json.address ?? null,
        network: json.network ?? 'mainnet',
        faucet_url: json.faucet_url ?? null,
        instructions: json.instructions ?? null,
        error: json.error ?? null,
        holdings: Array.isArray(json.holdings) ? json.holdings : [],
        total_usd: typeof json.total_usd === 'number' ? json.total_usd : 0,
      });
    } catch (e) {
      setData({
        address: null,
        network: 'mainnet',
        faucet_url: null,
        instructions: null,
        error: String(e),
        holdings: [],
        total_usd: 0,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      await fetchDashboard();
      if (cancelled) return;
    })();
    return () => { cancelled = true; };
  }, [fetchDashboard]);

  const copyAddress = () => {
    if (!data?.address) return;
    navigator.clipboard.writeText(data.address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const hasWallet = data?.address && !data?.error;

  return (
    <div className="flex-shrink-0 rounded-lg border border-[var(--color-gray-300)] bg-[var(--color-gray-50)] dark:bg-[var(--color-gray-900)] dark:border-[var(--color-gray-700)] overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm font-medium text-[var(--color-gray-900)] dark:text-[var(--color-gray-100)] hover:bg-[var(--color-gray-200)] dark:hover:bg-[var(--color-gray-800)] transition-colors"
      >
        <span className="flex items-center gap-2">
          <span>Wallet</span>
          {hasWallet && data?.address && (
            <>
              <span className="text-[var(--color-gray-500)]">·</span>
              <span className="font-mono text-xs truncate max-w-[120px]" title={data.address}>
                {data.address.slice(0, 10)}…
              </span>
            </>
          )}
          {hasWallet && !loading && (
            <span className="text-[var(--color-green-600)] dark:text-[var(--color-green-400)] font-semibold tabular-nums">
              {formatUsd(data.total_usd)}
            </span>
          )}
        </span>
        <span className="text-[var(--color-gray-500)]" aria-hidden>
          {expanded ? '▼' : '▶'}
        </span>
      </button>
      {expanded && (
        <div className="px-3 pb-3 pt-0 border-t border-[var(--color-gray-200)] dark:border-[var(--color-gray-700)] space-y-3">
          {loading && (
            <p className="text-sm text-[var(--color-gray-600)] dark:text-[var(--color-gray-400)] py-2">
              Loading…
            </p>
          )}
          {!loading && (data?.error || !data?.address) && (
            <p className="text-sm text-[var(--color-gray-600)] dark:text-[var(--color-gray-400)] py-2">
              {data?.error ?? 'No wallet configured. Ask Aura to create one.'}
            </p>
          )}
          {!loading && hasWallet && data && data.address && (
            <>
              {/* Balance summary */}
              <div className="pt-2 flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <div className="text-xs text-[var(--color-gray-500)] dark:text-[var(--color-gray-400)] uppercase tracking-wide">
                    Total balance
                  </div>
                  <div className="text-xl font-bold text-[var(--color-gray-900)] dark:text-[var(--color-gray-100)] tabular-nums">
                    {formatUsd(data.total_usd)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => { setLoading(true); fetchDashboard(); }}
                  className="text-xs font-medium px-2.5 py-1.5 rounded-md bg-[var(--color-gray-200)] dark:bg-[var(--color-gray-700)] text-[var(--color-gray-700)] dark:text-[var(--color-gray-300)] hover:bg-[var(--color-gray-300)] dark:hover:bg-[var(--color-gray-600)]"
                >
                  Refresh
                </button>
              </div>

              {/* Token list */}
              {data.holdings.length > 0 && (
                <div>
                  <div className="text-xs text-[var(--color-gray-500)] dark:text-[var(--color-gray-400)] uppercase tracking-wide mb-1.5">
                    Tokens
                  </div>
                  <div className="rounded-md border border-[var(--color-gray-200)] dark:border-[var(--color-gray-700)] overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-[var(--color-gray-200)] dark:bg-[var(--color-gray-800)] text-left text-xs text-[var(--color-gray-600)] dark:text-[var(--color-gray-400)]">
                          <th className="px-2 py-1.5 font-medium">Token</th>
                          <th className="px-2 py-1.5 font-medium text-right">Amount</th>
                          <th className="px-2 py-1.5 font-medium text-right">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.holdings.map((h) => (
                          <tr
                            key={h.symbol}
                            className="border-t border-[var(--color-gray-200)] dark:border-[var(--color-gray-700)]"
                          >
                            <td className="px-2 py-1.5 font-medium">{h.symbol}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">
                              {formatAmount(h.amount, h.symbol)}
                            </td>
                            <td className="px-2 py-1.5 text-right tabular-nums">
                              {formatUsd(h.value_usd)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Address + QR row */}
              <div className="flex flex-col sm:flex-row gap-3 items-start">
                <div className="flex-shrink-0 rounded-md overflow-hidden bg-white dark:bg-black p-1.5 border border-[var(--color-gray-200)] dark:border-[var(--color-gray-700)]">
                  <img
                    src={qrImageUrl(data.address, 160)}
                    alt="QR code to fund wallet"
                    width={160}
                    height={160}
                    className="block"
                  />
                </div>
                <div className="flex-1 min-w-0 flex flex-col gap-1.5">
                  <div className="text-xs text-[var(--color-gray-500)] dark:text-[var(--color-gray-400)]">
                    Address ({data.network})
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <code className="text-xs break-all font-mono bg-[var(--color-gray-200)] dark:bg-[var(--color-gray-800)] px-2 py-1 rounded">
                      {data.address}
                    </code>
                    <button
                      type="button"
                      onClick={copyAddress}
                      className="flex-shrink-0 text-xs font-medium px-2.5 py-1 rounded-md bg-[var(--color-blue-500)] text-white hover:bg-[var(--color-blue-600)]"
                    >
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  {data.instructions && (
                    <p className="text-xs text-[var(--color-gray-600)] dark:text-[var(--color-gray-300)]">
                      {data.instructions}
                    </p>
                  )}
                  {data.faucet_url && (
                    <a
                      href={data.faucet_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-medium text-[var(--color-blue-500)] hover:underline"
                    >
                      Get test SUI (faucet) →
                    </a>
                  )}
                  {/* Swap SUI → USDC on a dApp; connect this wallet there */}
                  <div className="pt-1 border-t border-[var(--color-gray-200)] dark:border-[var(--color-gray-700)] mt-1.5">
                    <p className="text-xs text-[var(--color-gray-600)] dark:text-[var(--color-gray-300)] mb-1.5">
                      Swap SUI → USDC on a dApp (connect this wallet): choose SUI → USDC, enter amount, confirm.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <a
                        href="https://deepbook.tech/trade-on-deepbook"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium px-2.5 py-1 rounded-md bg-[var(--color-gray-200)] dark:bg-[var(--color-gray-700)] text-[var(--color-gray-800)] dark:text-[var(--color-gray-200)] hover:bg-[var(--color-gray-300)] dark:hover:bg-[var(--color-gray-600)]"
                      >
                        DeepBook →
                      </a>
                      <a
                        href="https://suiswap.app/app/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium px-2.5 py-1 rounded-md bg-[var(--color-gray-200)] dark:bg-[var(--color-gray-700)] text-[var(--color-gray-800)] dark:text-[var(--color-gray-200)] hover:bg-[var(--color-gray-300)] dark:hover:bg-[var(--color-gray-600)]"
                      >
                        SuiSwap →
                      </a>
                      <a
                        href="https://www.dipcoin.io"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium px-2.5 py-1 rounded-md bg-[var(--color-gray-200)] dark:bg-[var(--color-gray-700)] text-[var(--color-gray-800)] dark:text-[var(--color-gray-200)] hover:bg-[var(--color-gray-300)] dark:hover:bg-[var(--color-gray-600)]"
                      >
                        DipCoin →
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
