#!/usr/bin/env python3
"""
Unit tests for DevOps Health Monitor
Run: python3 -m pytest tests/ -v
"""

import sys
import os
import json
import tempfile
import unittest

# Make app importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import monitor


class TestHealthEvaluation(unittest.TestCase):

    def _make_metrics(self, cpu=10, mem=20, disk=30, services=None):
        if services is None:
            services = {"docker": {"status": "running", "version": "v24"}}
        return {
            "system":   {"hostname": "testhost", "os": "Linux",
                         "kernel": "6.x", "arch": "x86_64",
                         "python": "3.11", "timestamp": "2025-01-01T00:00:00Z"},
            "cpu":      {"cpu_percent": cpu, "cores": 4},
            "memory":   {"memory_percent": mem, "total_gb": 8.0,
                         "used_gb": round(8*mem/100, 2), "available_gb": 0},
            "disk":     {"disk_percent": disk, "path": "/",
                         "total_gb": 100, "used_gb": disk, "free_gb": 100-disk},
            "services": services,
        }

    def test_healthy_system(self):
        metrics = self._make_metrics(cpu=10, mem=20, disk=30)
        health  = monitor.evaluate_health(metrics)
        self.assertEqual(health["status"], "HEALTHY")
        self.assertGreaterEqual(health["score"], 80)
        self.assertEqual(health["alerts"], [])

    def test_high_cpu_triggers_warning(self):
        metrics = self._make_metrics(cpu=95)
        monitor.THRESHOLDS["cpu_percent"] = 80
        health = monitor.evaluate_health(metrics)
        monitor.THRESHOLDS["cpu_percent"] = 80   # restore default
        # A CPU alert should be present even if score stays in HEALTHY range
        self.assertTrue(any("CPU" in a for a in health["alerts"]),
                        "Expected a CPU alert in alerts list")

    def test_high_memory_triggers_alert(self):
        metrics = self._make_metrics(mem=90)
        health  = monitor.evaluate_health(metrics)
        self.assertTrue(any("MEMORY" in a for a in health["alerts"]))

    def test_high_disk_triggers_alert(self):
        metrics = self._make_metrics(disk=95)
        health  = monitor.evaluate_health(metrics)
        self.assertTrue(any("DISK" in a for a in health["alerts"]))

    def test_stopped_service_alert(self):
        svcs    = {"docker": {"status": "stopped", "version": "N/A"}}
        metrics = self._make_metrics(services=svcs)
        health  = monitor.evaluate_health(metrics)
        self.assertTrue(any("docker" in a for a in health["alerts"]))

    def test_score_never_below_zero(self):
        metrics = self._make_metrics(cpu=99, mem=99, disk=99,
                                     services={"svc": {"status": "stopped",
                                                       "version": "N/A"}})
        health = monitor.evaluate_health(metrics)
        self.assertGreaterEqual(health["score"], 0)

    def test_critical_status_at_low_score(self):
        metrics = self._make_metrics(cpu=99, mem=99, disk=99)
        health  = monitor.evaluate_health(metrics)
        self.assertIn(health["status"], ["WARNING", "CRITICAL"])


class TestReportGeneration(unittest.TestCase):

    def _sample_report(self):
        metrics = {
            "system":   {"hostname": "h", "os": "Linux", "kernel": "6",
                         "arch": "x64", "python": "3.11",
                         "timestamp": "2025-01-01T00:00:00Z"},
            "cpu":      {"cpu_percent": 5, "cores": 2},
            "memory":   {"memory_percent": 30, "total_gb": 4,
                         "used_gb": 1.2, "available_gb": 2.8},
            "disk":     {"disk_percent": 40, "path": "/",
                         "total_gb": 50, "used_gb": 20, "free_gb": 30},
            "services": {},
        }
        health = monitor.evaluate_health(metrics)
        return monitor.build_report(metrics, health)

    def test_report_has_required_keys(self):
        report = self._sample_report()
        for key in ("report_version", "generated_at", "system", "health", "metrics"):
            self.assertIn(key, report)

    def test_save_report_creates_file(self):
        report = self._sample_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = monitor.save_report(report, tmpdir)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded["report_version"], "1.0")

    def test_report_version_field(self):
        report = self._sample_report()
        self.assertEqual(report["report_version"], "1.0")


class TestSystemInfoKeys(unittest.TestCase):

    def test_system_info_has_expected_keys(self):
        info = monitor.get_system_info()
        for key in ("hostname", "os", "kernel", "arch", "python", "timestamp"):
            self.assertIn(key, info)

    def test_disk_usage_returns_dict(self):
        result = monitor.get_disk_usage("/")
        self.assertIn("disk_percent", result)
        self.assertIsInstance(result["disk_percent"], (int, float))

    def test_memory_usage_returns_dict(self):
        result = monitor.get_memory_usage()
        self.assertIn("memory_percent", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
