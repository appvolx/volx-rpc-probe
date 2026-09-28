#!/usr/bin/env python3
"""
volx-rpc-probe — Local Solana RPC health & latency probe.

Client-side only. Uses public JSON-RPC methods. No credentials stored.
Part of the VOLX (https://volx.app) ecosystem tooling.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://rpc.ankr.com/solana",
    "https://solana-rpc.publicnode.com",
    "https://solana.drpc.org",
]

METHODS = [
    ("getHealth", []),
    ("getVersion", []),
    ("getSlot", [{"commitment": "confirmed"}]),
]


@dataclass
class EndpointResult:
    url: str
    ok: bool
    latencies_ms: list[float] = field(default_factory=list)
    slot: int | None = None
    version: str | None = None
    health: str | None = None
    error: str | None = None
    samples: int = 0

    @property
    def avg_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        return statistics.mean(self.latencies_ms)

    @property
    def min_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        return min(self.latencies_ms)

    @property
    def max_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        return max(self.latencies_ms)


def rpc_call(
    url: str,
    method: str,
    params: list[Any],
    timeout: float,
    request_id: int = 1,
) -> tuple[Any, float]:
    """Perform a single JSON-RPC call. Returns (result, latency_ms)."""
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "volx-rpc-probe/1.0 (+https://volx.app)",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    latency = (time.perf_counter() - t0) * 1000.0
    parsed = json.loads(body.decode("utf-8"))
    if "error" in parsed and parsed["error"]:
        raise RuntimeError(str(parsed["error"]))
    return parsed.get("result"), latency


def probe_endpoint(
    url: str,
    samples: int,
    timeout: float,
    commitment: str,
) -> EndpointResult:
    result = EndpointResult(url=url, ok=False)
    try:
        # Health
        health, lat = rpc_call(url, "getHealth", [], timeout)
        result.health = str(health) if health is not None else "ok"
        result.latencies_ms.append(lat)

        # Version
        version, lat = rpc_call(url, "getVersion", [], timeout)
        if isinstance(version, dict):
            result.version = version.get("solana-core") or str(version)
        else:
            result.version = str(version)
        result.latencies_ms.append(lat)

        # Slot samples
        for i in range(samples):
            slot, lat = rpc_call(
                url,
                "getSlot",
                [{"commitment": commitment}],
                timeout,
                request_id=10 + i,
            )
            result.latencies_ms.append(lat)
            if isinstance(slot, int):
                result.slot = slot

        result.ok = True
        result.samples = len(result.latencies_ms)
    except Exception as exc:  # noqa: BLE001 — surface any RPC/network error
        result.error = f"{type(exc).__name__}: {exc}"
        result.ok = False
    return result


def format_table(results: list[EndpointResult]) -> str:
    lines = []
    header = (
        f"{'Endpoint':<45} {'OK':<4} {'Avg ms':>8} {'Min':>7} {'Max':>7} "
        f"{'Slot':>12} {'Version':<16} Error"
    )
    lines.append(header)
    lines.append("-" * len(header))

    max_slot = max((r.slot or 0 for r in results if r.ok), default=0)

    for r in sorted(results, key=lambda x: (not x.ok, x.avg_ms or 99999)):
        lag = ""
        if r.ok and r.slot and max_slot:
            delta = max_slot - r.slot
            if delta > 0:
                lag = f" (lag {delta})"
        avg = f"{r.avg_ms:.1f}" if r.avg_ms is not None else "-"
        mn = f"{r.min_ms:.1f}" if r.min_ms is not None else "-"
        mx = f"{r.max_ms:.1f}" if r.max_ms is not None else "-"
        slot_s = f"{r.slot}{lag}" if r.slot else "-"
        ver = (r.version or "-")[:15]
        err = (r.error or "")[:40]
        lines.append(
            f"{r.url:<45} {'yes' if r.ok else 'no':<4} {avg:>8} {mn:>7} {mx:>7} "
            f"{slot_s:>12} {ver:<16} {err}"
        )
    return "\n".join(lines)


def run_once(
    endpoints: list[str],
    samples: int,
    timeout: float,
    commitment: str,
    as_json: bool,
) -> list[EndpointResult]:
    results: list[EndpointResult] = []
    with ThreadPoolExecutor(max_workers=min(8, len(endpoints) or 1)) as pool:
        futures = {
            pool.submit(probe_endpoint, url, samples, timeout, commitment): url
            for url in endpoints
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    if as_json:
        payload = []
        for r in results:
            d = asdict(r)
            d["avg_ms"] = r.avg_ms
            d["min_ms"] = r.min_ms
            d["max_ms"] = r.max_ms
            payload.append(d)
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(results))
        ok_count = sum(1 for r in results if r.ok)
        print(f"\n{ok_count}/{len(results)} endpoints healthy")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="volx-rpc-probe",
        description="Local Solana RPC health & latency probe for VOLX (volx.app)",
    )
    parser.add_argument(
        "--endpoints",
        default=",".join(DEFAULT_ENDPOINTS),
        help="Comma-separated RPC URLs",
    )
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--watch", type=int, default=0, help="Repeat every N seconds")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--commitment",
        default="confirmed",
        choices=["processed", "confirmed", "finalized"],
    )
    args = parser.parse_args(argv)

    endpoints = [u.strip() for u in args.endpoints.split(",") if u.strip()]
    if not endpoints:
        print("No endpoints provided", file=sys.stderr)
        return 2

    while True:
        run_once(endpoints, args.samples, args.timeout, args.commitment, args.json)
        if args.watch <= 0:
            break
        time.sleep(args.watch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
