#!/usr/bin/env python3
"""
Prometheus Metrics Consumer for Login-App
This script queries Prometheus for CPU and memory metrics of login-app pods.

Usage:
  1. Port-forward Prometheus: kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
  2. Run script: python3 prometheus_monitor.py
  
Or for continuous monitoring:
  python3 prometheus_monitor.py --interval 5
"""

import requests
import json
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional

class PrometheusMonitor:
    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        """Initialize Prometheus monitor with the Prometheus server URL."""
        self.prometheus_url = prometheus_url
        self.query_url = f"{prometheus_url}/api/v1/query"
        
    def query_prometheus(self, query: str) -> Optional[Dict]:
        """Execute a PromQL query and return the results."""
        try:
            response = requests.get(self.query_url, params={'query': query}, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying Prometheus: {e}")
            return None
    
    def get_cpu_usage(self) -> List[Dict]:
        """Get CPU usage for login-app pods in millicores."""
        # Query: CPU usage rate per pod
        query = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"login-app.*",container!=""}[5m])) by (pod) * 1000'
        result = self.query_prometheus(query)
        
        metrics = []
        if result and result.get('status') == 'success':
            for item in result['data']['result']:
                pod_name = item['metric']['pod']
                cpu_millicores = float(item['value'][1])
                metrics.append({
                    'pod': pod_name,
                    'cpu_millicores': round(cpu_millicores, 2),
                    'cpu_cores': round(cpu_millicores / 1000, 3)
                })
        return metrics
    
    def get_memory_usage(self) -> List[Dict]:
        """Get memory usage for login-app pods in MB."""
        # Query: Memory working set per pod
        query = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"login-app.*",container!=""}) by (pod)'
        result = self.query_prometheus(query)
        
        metrics = []
        if result and result.get('status') == 'success':
            for item in result['data']['result']:
                pod_name = item['metric']['pod']
                memory_bytes = float(item['value'][1])
                memory_mb = memory_bytes / (1024 * 1024)
                memory_gb = memory_bytes / (1024 * 1024 * 1024)
                metrics.append({
                    'pod': pod_name,
                    'memory_bytes': int(memory_bytes),
                    'memory_mb': round(memory_mb, 2),
                    'memory_gb': round(memory_gb, 3)
                })
        return metrics
    
    def get_network_stats(self) -> Dict[str, List[Dict]]:
        """Get network receive and transmit rates for login-app pods."""
        # Network receive rate
        rx_query = 'sum(rate(container_network_receive_bytes_total{namespace="default",pod=~"login-app.*"}[5m])) by (pod)'
        tx_query = 'sum(rate(container_network_transmit_bytes_total{namespace="default",pod=~"login-app.*"}[5m])) by (pod)'
        
        rx_result = self.query_prometheus(rx_query)
        tx_result = self.query_prometheus(tx_query)
        
        rx_metrics = []
        tx_metrics = []
        
        if rx_result and rx_result.get('status') == 'success':
            for item in rx_result['data']['result']:
                pod_name = item['metric']['pod']
                rx_bytes_per_sec = float(item['value'][1])
                rx_metrics.append({
                    'pod': pod_name,
                    'rx_bytes_per_sec': round(rx_bytes_per_sec, 2),
                    'rx_kb_per_sec': round(rx_bytes_per_sec / 1024, 2),
                    'rx_mb_per_sec': round(rx_bytes_per_sec / (1024 * 1024), 3)
                })
        
        if tx_result and tx_result.get('status') == 'success':
            for item in tx_result['data']['result']:
                pod_name = item['metric']['pod']
                tx_bytes_per_sec = float(item['value'][1])
                tx_metrics.append({
                    'pod': pod_name,
                    'tx_bytes_per_sec': round(tx_bytes_per_sec, 2),
                    'tx_kb_per_sec': round(tx_bytes_per_sec / 1024, 2),
                    'tx_mb_per_sec': round(tx_bytes_per_sec / (1024 * 1024), 3)
                })
        
        return {'receive': rx_metrics, 'transmit': tx_metrics}
    
    def get_pod_restarts(self) -> List[Dict]:
        """Get restart count for login-app pods."""
        query = 'kube_pod_container_status_restarts_total{namespace="default",pod=~"login-app.*"}'
        result = self.query_prometheus(query)
        
        metrics = []
        if result and result.get('status') == 'success':
            for item in result['data']['result']:
                pod_name = item['metric']['pod']
                restarts = int(float(item['value'][1]))
                metrics.append({
                    'pod': pod_name,
                    'restarts': restarts
                })
        return metrics
    
    def display_metrics(self):
        """Fetch and display all metrics in a formatted way."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*80}")
        print(f"Login-App Metrics - {timestamp}")
        print(f"{'='*80}\n")
        
        # CPU Metrics
        print("📊 CPU Usage:")
        print(f"{'Pod Name':<40} {'CPU (millicores)':<20} {'CPU (cores)':<15}")
        print("-" * 80)
        cpu_metrics = self.get_cpu_usage()
        if cpu_metrics:
            total_cpu = 0
            for metric in cpu_metrics:
                print(f"{metric['pod']:<40} {metric['cpu_millicores']:<20} {metric['cpu_cores']:<15}")
                total_cpu += metric['cpu_millicores']
            print("-" * 80)
            print(f"{'TOTAL':<40} {round(total_cpu, 2):<20} {round(total_cpu/1000, 3):<15}")
        else:
            print("No CPU metrics available")
        
        # Memory Metrics
        print(f"\n💾 Memory Usage:")
        print(f"{'Pod Name':<40} {'Memory (MB)':<20} {'Memory (GB)':<15}")
        print("-" * 80)
        memory_metrics = self.get_memory_usage()
        if memory_metrics:
            total_memory_mb = 0
            for metric in memory_metrics:
                print(f"{metric['pod']:<40} {metric['memory_mb']:<20} {metric['memory_gb']:<15}")
                total_memory_mb += metric['memory_mb']
            print("-" * 80)
            print(f"{'TOTAL':<40} {round(total_memory_mb, 2):<20} {round(total_memory_mb/1024, 3):<15}")
        else:
            print("No memory metrics available")
        
        # Network Metrics
        print(f"\n🌐 Network Statistics:")
        network_stats = self.get_network_stats()
        
        print(f"\n  Network Receive:")
        print(f"  {'Pod Name':<38} {'Bytes/s':<15} {'KB/s':<15} {'MB/s':<15}")
        print("  " + "-" * 78)
        if network_stats['receive']:
            for metric in network_stats['receive']:
                print(f"  {metric['pod']:<38} {metric['rx_bytes_per_sec']:<15} {metric['rx_kb_per_sec']:<15} {metric['rx_mb_per_sec']:<15}")
        else:
            print("  No receive metrics available")
        
        print(f"\n  Network Transmit:")
        print(f"  {'Pod Name':<38} {'Bytes/s':<15} {'KB/s':<15} {'MB/s':<15}")
        print("  " + "-" * 78)
        if network_stats['transmit']:
            for metric in network_stats['transmit']:
                print(f"  {metric['pod']:<38} {metric['tx_bytes_per_sec']:<15} {metric['tx_kb_per_sec']:<15} {metric['tx_mb_per_sec']:<15}")
        else:
            print("  No transmit metrics available")
        
        # Pod Restarts
        print(f"\n🔄 Pod Restarts:")
        print(f"{'Pod Name':<40} {'Restart Count':<20}")
        print("-" * 80)
        restart_metrics = self.get_pod_restarts()
        if restart_metrics:
            for metric in restart_metrics:
                print(f"{metric['pod']:<40} {metric['restarts']:<20}")
        else:
            print("No restart metrics available")
        
        print(f"\n{'='*80}\n")
    
    def export_to_json(self, filename: str = "login_app_metrics.json"):
        """Export all metrics to a JSON file."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'network': self.get_network_stats(),
            'restarts': self.get_pod_restarts()
        }
        
        with open(filename, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"Metrics exported to {filename}")


def main():
    parser = argparse.ArgumentParser(description='Monitor login-app metrics from Prometheus')
    parser.add_argument('--url', default='http://localhost:9090', 
                       help='Prometheus URL (default: http://localhost:9090)')
    parser.add_argument('--interval', type=int, default=0,
                       help='Refresh interval in seconds (0 = run once)')
    parser.add_argument('--export', action='store_true',
                       help='Export metrics to JSON file')
    parser.add_argument('--output', default='login_app_metrics.json',
                       help='Output JSON filename (default: login_app_metrics.json)')
    
    args = parser.parse_args()
    
    monitor = PrometheusMonitor(prometheus_url=args.url)
    
    # Test connection
    print(f"Connecting to Prometheus at {args.url}...")
    test_result = monitor.query_prometheus('up')
    if not test_result:
        print("\n❌ Error: Cannot connect to Prometheus!")
        print("\nMake sure to port-forward Prometheus first:")
        print("kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090")
        return 1
    
    print("✅ Connected successfully!\n")
    
    try:
        if args.interval > 0:
            print(f"Starting continuous monitoring (refresh every {args.interval}s, press Ctrl+C to stop)...\n")
            while True:
                monitor.display_metrics()
                if args.export:
                    monitor.export_to_json(args.output)
                time.sleep(args.interval)
        else:
            monitor.display_metrics()
            if args.export:
                monitor.export_to_json(args.output)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        return 0
    
    return 0


if __name__ == "__main__":
    exit(main())
