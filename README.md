# volx-rpc-probe

**VOLX Ecosystem Tool** — Local Solana RPC health & latency probe.

Part of the [VOLX](https://volx.app) tooling suite.  
GitHub org: [https://github.com/appvolx](https://github.com/appvolx)

## What it does

`volx-rpc-probe` is a **client-side / local-only** utility that measures the health, latency, and basic capability of public (or your own) Solana RPC endpoints.

It never stores credentials, never opens inbound ports, and never sends private keys.  
It only performs standard JSON-RPC calls (`getHealth`, `getSlot`, `getVersion`, `getRecentPerformanceSamples`, etc.) against endpoints you supply or the built-in public list.

## Why it exists

VOLX (and any serious Solana dApp) depends on reliable RPC. Public endpoints such as `https://api.mainnet-beta.solana.com` are rate-limited and occasionally return 403 on heavier methods. This tool helps you:

- Compare latency across multiple public providers
- Detect endpoints that reject certain methods
- Produce a simple ranking before you point `NEXT_PUBLIC_SOLANA_RPC_URL` at a paid provider
- Run continuous local monitoring without exposing secrets

## Features

- Parallel probing of multiple endpoints
- Configurable timeout and commitment level
- Latency (min / avg / max) and success rate
- Slot lag estimation relative to the fastest responding node
- Optional continuous watch mode
- Pure Python 3.10+, zero external dependencies for core mode
- Optional `httpx` for async mode

## Requirements

- Python ≥ 3.10
- No API keys required
- Internet access only to the RPC endpoints you list

## Installation

```bash
# Clone or extract this folder
cd volx-rpc-probe

# Optional virtualenv
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Core mode needs only stdlib
# Optional better HTTP client:
pip install -r requirements.txt
```

## Quick start

```bash
# Probe the default public endpoints
python -m src.probe

# Probe your own list
python -m src.probe --endpoints https://api.mainnet-beta.solana.com,https://rpc.ankr.com/solana

# Continuous watch every 30 s
python -m src.probe --watch 30

# JSON output for scripting
python -m src.probe --json
```

## CLI options

| Flag | Description |
|------|-------------|
| `--endpoints` | Comma-separated list of RPC URLs (overrides defaults) |
| `--timeout` | Per-request timeout in seconds (default: 8) |
| `--samples` | Number of latency samples per endpoint (default: 3) |
| `--watch N` | Repeat every N seconds (0 = once) |
| `--json` | Machine-readable JSON output |
| `--commitment` | Solana commitment (`processed` / `confirmed` / `finalized`) |

## Default public endpoints

The tool ships with a small set of well-known public endpoints.  
**These are rate-limited.** Prefer your own Helius / QuickNode / Triton / Alchemy URL for production use inside VOLX.

## Security model

- No private keys, seed phrases, or session secrets are ever read or written
- No credentials are accepted on the command line or environment for RPC authentication (use URL query params only if your provider requires them, and keep them out of git)
- All network traffic is outbound HTTPS to the endpoints you specify
- Suitable for public GitHub repositories

## Integration with VOLX

After you find a healthy endpoint, set it in the VOLX monorepo:

```bash
# .env.local (never commit)
NEXT_PUBLIC_SOLANA_RPC_URL=https://your-preferred-rpc.example
```

See the main VOLX repository (`src/lib/solana/connection.ts`) for how the app selects the RPC endpoint.

## License

MIT — complementary tooling for the VOLX project (https://volx.app).

## Disclaimer

This tool only talks to public JSON-RPC interfaces. It does not interact with wallets, does not sign transactions, and cannot move funds. Use at your own risk.
