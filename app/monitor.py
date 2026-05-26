#!/usr/bin/env python3
"""
DevOps Health Monitor
Collects system metrics and generates health reports.
"""

import os
import sys
import json
import shutil
import platform
import subprocess
import argparse
from datetime import datetime


# ── Thresholds ────────────────────────────────────────────────────────────────
THRESHOLDS = {
    "cpu_percent":    float(os.getenv("THRESHOLD_CPU",  "80")),
    "memory_percent": float(os.getenv("THRESHOLD_MEM",  "85")),
    "disk_percent":   float(os.getenv("THRESHOLD_DISK", "90")),
}


# ── Collectors ────────────────────────────────────────────────────────────────
def get_cpu_usage() -> dict:
    """Read CPU usage from /proc/stat (Linux-native, no extra deps)."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()          # cpu  user nice system idle …
        fields = list(map(int, line.split()[1:]))
        idle, total = fields[3], sum(fields)

        import time
        time.sleep(0.1)

        with open("/proc/stat") as f:
            line = f.readline()
        fields2 = list(map(int, line.split()[1:]))
        idle2, total2 = fields2[3], sum(fields2)

        diff_idle  = idle2  - idle
        diff_total = total2 - total
        percent = 100.0 * (1 - diff_idle / diff_total) if diff_total else 0.0
        return {"cpu_percent": round(percent, 1), "cores": os.cpu_count() or 1}
    except Exception as exc:
        return {"cpu_percent": 0.0, "cores": 1, "error": str(exc)}


def get_memory_usage() -> dict:
    """Read memory info from /proc/meminfo."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k.strip()] = int(v.split()[0])   # kB values

        total     = info["MemTotal"]
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used      = total - available
        percent   = round(100.0 * used / total, 1) if total else 0.0

        def kb_to_gb(kb): return round(kb / 1_048_576, 2)
        return {
            "total_gb":      kb_to_gb(total),
            "used_gb":       kb_to_gb(used),
            "available_gb":  kb_to_gb(available),
            "memory_percent": percent,
        }
    except Exception as exc:
        return {"memory_percent": 0.0, "error": str(exc)}


def get_disk_usage(path: str = "/") -> dict:
    """Use shutil.disk_usage (stdlib, cross-platform)."""
    try:
        usage = shutil.disk_usage(path)
        percent = round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0
        def b_to_gb(b): return round(b / 1_073_741_824, 2)
        return {
            "path":         path,
            "total_gb":     b_to_gb(usage.total),
            "used_gb":      b_to_gb(usage.used),
            "free_gb":      b_to_gb(usage.free),
            "disk_percent": percent,
        }
    except Exception as exc:
        return {"disk_percent": 0.0, "error": str(exc)}


def get_running_services() -> dict:
    """Check common services via shell commands available inside the container."""
    services = {}
    checks = {
        "docker":  ["docker", "info"],
        "git":     ["git",    "--version"],
        "python3": ["python3","--version"],
        "bash":    ["bash",   "--version"],
    }
    for name, cmd in checks.items():
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            )
            services[name] = {
                "status":  "running" if result.returncode == 0 else "stopped",
                "version": (result.stdout or result.stderr).strip().splitlines()[0],
            }
        except FileNotFoundError:
            services[name] = {"status": "not_found", "version": "N/A"}
        except Exception as exc:
            services[name] = {"status": "error", "version": str(exc)}
    return services


def get_system_info() -> dict:
    return {
        "hostname":  platform.node()   or os.getenv("HOSTNAME", "unknown"),
        "os":        platform.system(),
        "kernel":    platform.release(),
        "arch":      platform.machine(),
        "python":    platform.python_version(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Health evaluation ─────────────────────────────────────────────────────────
def evaluate_health(metrics: dict) -> dict:
    alerts, score = [], 100

    cpu = metrics["cpu"]["cpu_percent"]
    mem = metrics["memory"]["memory_percent"]
    dsk = metrics["disk"]["disk_percent"]

    checks = [
        ("cpu",    cpu, THRESHOLDS["cpu_percent"],    10),
        ("memory", mem, THRESHOLDS["memory_percent"], 15),
        ("disk",   dsk, THRESHOLDS["disk_percent"],   20),
    ]
    for name, value, threshold, penalty in checks:
        if value > threshold:
            alerts.append(f"HIGH {name.upper()}: {value}% (threshold {threshold}%)")
            score -= penalty

    stopped = [
        svc for svc, info in metrics["services"].items()
        if info["status"] != "running"
    ]
    if stopped:
        alerts.append(f"Services not running: {', '.join(stopped)}")
        score -= 5 * len(stopped)

    score = max(score, 0)
    status = "HEALTHY" if score >= 80 else ("WARNING" if score >= 50 else "CRITICAL")

    return {"status": status, "score": score, "alerts": alerts}


# ── Report generation ─────────────────────────────────────────────────────────
def build_report(metrics: dict, health: dict) -> dict:
    return {
        "report_version": "1.0",
        "generated_at":   metrics["system"]["timestamp"],
        "system":         metrics["system"],
        "health":         health,
        "metrics":        metrics,
    }


def save_report(report: dict, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"health_report_{ts}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path


def print_summary(report: dict) -> None:
    h  = report["health"]
    m  = report["metrics"]
    si = report["system"]

    status_color = {
        "HEALTHY":  "\033[92m",   # green
        "WARNING":  "\033[93m",   # yellow
        "CRITICAL": "\033[91m",   # red
    }.get(h["status"], "")
    RESET = "\033[0m"

    print("\n" + "=" * 60)
    print("  DevOps System Health Monitor")
    print("=" * 60)
    print(f"  Host      : {si['hostname']}")
    print(f"  OS        : {si['os']} {si['kernel']}")
    print(f"  Timestamp : {si['timestamp']}")
    print("-" * 60)
    print(f"  Status    : {status_color}{h['status']}{RESET}  (score {h['score']}/100)")
    print("-" * 60)
    print(f"  CPU       : {m['cpu']['cpu_percent']}%   ({m['cpu']['cores']} cores)")
    print(f"  Memory    : {m['memory']['memory_percent']}%   "
          f"({m['memory'].get('used_gb','?')} / {m['memory'].get('total_gb','?')} GB)")
    print(f"  Disk ({m['disk']['path']}) : {m['disk']['disk_percent']}%   "
          f"({m['disk'].get('used_gb','?')} / {m['disk'].get('total_gb','?')} GB)")
    print("-" * 60)
    print("  Services:")
    for svc, info in m["services"].items():
        icon = "✓" if info["status"] == "running" else "✗"
        print(f"    {icon} {svc:<12} {info['status']:<12} {info['version'][:40]}")
    if h["alerts"]:
        print("-" * 60)
        print("  ⚠ Alerts:")
        for a in h["alerts"]:
            print(f"    • {a}")
    print("=" * 60 + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="DevOps Health Monitor")
    parser.add_argument("--output-dir", default="reports",
                        help="Directory for JSON reports (default: reports/)")
    parser.add_argument("--json", action="store_true",
                        help="Print full JSON report to stdout")
    parser.add_argument("--no-save", action="store_true",
                        help="Skip saving report to disk")
    args = parser.parse_args()

    print("Collecting metrics …")
    metrics = {
        "system":   get_system_info(),
        "cpu":      get_cpu_usage(),
        "memory":   get_memory_usage(),
        "disk":     get_disk_usage(),
        "services": get_running_services(),
    }

    health = evaluate_health(metrics)
    report = build_report(metrics, health)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)

    if not args.no_save:
        path = save_report(report, args.output_dir)
        print(f"Report saved → {path}")

    # Exit code reflects health status
    exit_codes = {"HEALTHY": 0, "WARNING": 1, "CRITICAL": 2}
    sys.exit(exit_codes.get(health["status"], 2))


if __name__ == "__main__":
    main()
