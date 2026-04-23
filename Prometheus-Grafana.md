# Kubernetes Monitoring with Prometheus and Grafana

This guide provides comprehensive instructions for setting up monitoring in your Kubernetes cluster to collect metrics for autoscaling decisions and operational insights.

## Table of Contents
- Verification (If Already Installed)
- Installing Metrics Server
- Setting Up Prometheus and Grafana
- Accessing and Configuring Grafana
- Instrumenting Your Application
- Creating Custom Dashboards
- Setting Up Horizontal Pod Autoscaler (HPA)
- Load Testing for Autoscaling
- Troubleshooting

## Verification (If Already Installed)

If Prometheus and Grafana are already installed in your cluster, verify the installation:

```bash
# Check metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Verify metrics collection
kubectl top nodes
kubectl top pods

# Check Prometheus and Grafana pods
kubectl get pods -n monitoring

# Check Grafana service and port
kubectl get svc -n monitoring prometheus-grafana

# Verify HPA configuration
kubectl get hpa
kubectl describe hpa login-app-hpa
```

**Current Cluster Status:**
- **Grafana URL**: http://10.34.7.115:32432 or http://10.34.7.5:32432
- **Grafana Login**: admin / admin
- **Prometheus**: Running in monitoring namespace
- **Metrics Server**: Active and collecting metrics
- **HPA**: Configured for login-app (2-4 replicas, CPU target 80%)

If all components are running, skip to the "Accessing and Configuring Grafana" section. Otherwise, continue with the installation steps below.

## Installing Metrics Server

Metrics Server collects resource metrics from Kubelets and exposes them in the Kubernetes API server for use by the Horizontal Pod Autoscaler.

```bash
git clone https://github.com/Widhi-yahya/kubernetes_installation_docker.git
cd kubernetes_installation_docker/
kubectl apply -f metrics-server.yaml

# Verify metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Test that metrics are being collected
kubectl top nodes
kubectl top pods -A
```

## Setting Up Prometheus and Grafana

Prometheus is used for collecting and storing metrics, while Grafana provides visualization.

### Installing with Helm

```bash
# Add Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create a monitoring namespace
kubectl create namespace monitoring

# Install Prometheus stack (includes Grafana)
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set grafana.adminPassword=admin \
  --set grafana.service.type=NodePort

# Verify installation
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

### Verify Prometheus Components

```bash
# Check Prometheus components
kubectl get pods -n monitoring | grep prometheus

# Check Alertmanager
kubectl get pods -n monitoring | grep alertmanager

# Check Grafana
kubectl get pods -n monitoring | grep grafana

# Get Grafana service details
kubectl get svc -n monitoring prometheus-grafana
```

## Accessing and Configuring Grafana

After deploying the Prometheus stack, you can access Grafana to visualize your metrics.

```bash
# Get Grafana service NodePort
export GRAFANA_PORT=$(kubectl get svc -n monitoring prometheus-grafana -o jsonpath='{.spec.ports[0].nodePort}')
echo "Access Grafana at http://<your-node-ip>:$GRAFANA_PORT"

# Login credentials:
# Username: admin
# Password: admin (or the password you set in the Helm installation)
```

### Access Grafana Dashboard

**For this cluster, Grafana is accessible at:**
- http://10.34.7.115:32432
- http://10.34.7.5:32432

**Login credentials:**
- Username: `admin`
- Password: `admin`

### Verify Prometheus and Grafana Installation

```bash
# Check all monitoring pods are running
kubectl get pods -n monitoring

# Verify Grafana service
kubectl get svc -n monitoring prometheus-grafana

# Verify metrics collection is working
kubectl top nodes
kubectl top pods

# Check HPA status
kubectl get hpa
kubectl describe hpa login-app-hpa
```

### Access Prometheus UI (Optional)

While Grafana is the primary interface, you can also access Prometheus directly for troubleshooting:

```bash
# Port-forward Prometheus to your local machine
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Then access http://localhost:9090 in your browser
# Useful URLs:
# - http://localhost:9090/targets (check scraping targets)
# - http://localhost:9090/graph (run PromQL queries)
# - http://localhost:9090/alerts (view active alerts)
```

**Note**: Port-forwarding is required for Prometheus as it's not exposed via NodePort by default.

## Instrumenting Your Application

To get custom metrics from your Node.js application, add Prometheus instrumentation:

### For Node.js Applications:

```javascript
// Add these to your package.json dependencies
// "prom-client": "^14.0.1",
// "express-prom-bundle": "^6.4.1"

// In your server.js:
const promBundle = require("express-prom-bundle");

// Add prometheus middleware
const metricsMiddleware = promBundle({
  includeMethod: true,
  includePath: true,
  promClient: {
    collectDefaultMetrics: {
      // Collect every 5 seconds
      timeout: 5000
    }
  }
});

// Use the middleware early in your Express app
app.use(metricsMiddleware);

// Your metrics will be available at the /metrics endpoint
```

### ServiceMonitor for Your Applications

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: login-app-monitor
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: login-app
  endpoints:
  - port: http  # Make sure this matches your service port name
    interval: 15s
    path: /metrics
  namespaceSelector:
    matchNames:
    - default  # Namespace where your app is running
```

Apply this configuration:

```bash
kubectl apply -f login-app-monitor.yaml
```

## Creating Custom Dashboards

### Import Built-in Kubernetes Dashboards

1. Access Grafana UI
2. Navigate to "+" icon on the left sidebar
3. Select "Import"
4. Enter the following dashboard IDs:
   - 6417 (Kubernetes Cluster)
   - 8588 (Kubernetes Deployment)
   - 11663 (Kubernetes Pod Monitoring)

### Create Network Metrics Dashboard

In Grafana:

1. Create a new dashboard
2. Add a panel for Network Received:
   ```
   sum(rate(container_network_receive_bytes_total{namespace="default",pod=~"login-app.*"}[5m])) by (pod)
   ```

3. Add a panel for Network Transmitted:
   ```
   sum(rate(container_network_transmit_bytes_total{namespace="default",pod=~"login-app.*"}[5m])) by (pod)
   ```

4. Add a panel for CPU Usage:
   ```
   sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"login-app.*"}[5m])) by (pod)
   ```

5. Add a panel for Memory Usage:
   ```
   sum(container_memory_working_set_bytes{namespace="default",pod=~"login-app.*"}) by (pod)
   ```

## Setting Up Horizontal Pod Autoscaler (HPA)

### Current HPA Configuration

The cluster already has an HPA configured for the login-app:

```bash
# Check current HPA status
kubectl get hpa login-app-hpa

# View detailed HPA configuration
kubectl describe hpa login-app-hpa
```

**Current Configuration:**
- Min replicas: 2
- Max replicas: 4
- CPU target: 80% utilization
- Scale up: 4 pods per 15 seconds or 100% per 15 seconds (whichever is higher)
- Scale down: Stabilization window of 300 seconds

### CPU-based HPA (Example for New Deployments)

If you need to create a new HPA or modify the existing one:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: login-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: login-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
```

Apply this configuration:

```bash
kubectl apply -f cpu-hpa.yaml

# Verify the HPA was created/updated
kubectl get hpa login-app-hpa
```

### Custom Metrics HPA (Network-based)

First, install Prometheus Adapter:

```bash
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring \
  --values - <<EOF
prometheus:
  url: http://prometheus-operated.monitoring.svc
  port: 9090
rules:
  default: false
  custom:
  - seriesQuery: 'container_network_receive_bytes_total{namespace!="",pod!=""}'
    resources:
      overrides:
        namespace: {resource: "namespace"}
        pod: {resource: "pod"}
    name:
      matches: "^(.*)_total"
      as: "${1}_per_second"
    metricsQuery: 'sum(rate(<<.Series>>{<<.LabelMatchers>>}[5m])) by (<<.GroupBy>>)'
EOF
```

Create network-based HPA:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: login-app-network-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: login-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Pods
    pods:
      metric:
        name: container_network_receive_bytes_per_second
      target:
        type: AverageValue
        averageValue: 1000000  # 1MB/s
```

Apply this configuration:

```bash
kubectl apply -f network-hpa.yaml
```

## Load Testing for Autoscaling

To test autoscaling, generate load on your application:

### Install Load Testing Tool

```bash
# Option 1: Install hey for load testing
go install github.com/rakyll/hey@latest

# Option 2: Use Apache Bench (if already installed)
which ab

# Option 3: Use kubectl run with busybox for simple testing
kubectl run -it --rm load-generator --image=busybox /bin/sh
# Then inside the pod:
while true; do wget -q -O- http://login-app; done
```

### Run Load Tests

```bash
# Using hey (if installed)
hey -z 5m -c 50 http://10.34.7.115:30080/

# Using Apache Bench
ab -n 10000 -c 50 http://10.34.7.115:30080/

# Using a simple shell loop
for i in {1..1000}; do curl http://10.34.7.115:30080/ & done

# Watch HPA scale in real-time
kubectl get hpa login-app-hpa -w

# Monitor pods scaling up/down in another terminal
kubectl get pods -w -l app=login-app
```

### Monitor CPU Usage During Load Test

```bash
# Watch CPU metrics
watch kubectl top pods -l app=login-app

# Check HPA events
kubectl describe hpa login-app-hpa | tail -20
```

## Monitoring Autoscaling

```bash
# Get HPA status
kubectl get hpa

# Get detailed HPA description
kubectl describe hpa login-app-hpa

# Check current metric values
kubectl get --raw "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods" | jq .
```

## Python Monitoring Script

A Python script (`prometheus_monitor.py`) is provided to query and display login-app metrics from Prometheus.

### Features

- Display CPU usage (millicores and cores) per pod
- Show memory usage (MB and GB) per pod
- Network statistics (receive/transmit rates)
- Pod restart counts
- Continuous monitoring with refresh intervals
- Export metrics to JSON file

### Installation

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Or install manually
pip3 install requests
```

### Usage

**1. Port-forward Prometheus (required):**

```bash
# In one terminal, forward Prometheus to localhost
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

**2. Run the monitoring script:**

```bash
# Single snapshot
python3 prometheus_monitor.py

# Continuous monitoring (refresh every 5 seconds)
python3 prometheus_monitor.py --interval 5

# Export to JSON
python3 prometheus_monitor.py --export --output metrics.json

# Continuous monitoring with JSON export
python3 prometheus_monitor.py --interval 10 --export
```

**3. Using a different Prometheus URL:**

```bash
# If Prometheus is accessible via different URL
python3 prometheus_monitor.py --url http://10.34.7.115:30119
```

### Script Options

```
--url        Prometheus URL (default: http://localhost:9090)
--interval   Refresh interval in seconds (0 = run once)
--export     Export metrics to JSON file
--output     Output JSON filename (default: login_app_metrics.json)
```

### Example Output

```
================================================================================
Login-App Metrics - 2026-04-14 10:30:45
================================================================================

📊 CPU Usage:
Pod Name                                 CPU (millicores)     CPU (cores)    
--------------------------------------------------------------------------------
login-app-544d5c5674-c4bc5              12.45                0.012          
login-app-544d5c5674-w9qdj              15.30                0.015          
login-app-544d5c5674-xwljs              10.80                0.011          
--------------------------------------------------------------------------------
TOTAL                                    38.55                0.039          

💾 Memory Usage:
Pod Name                                 Memory (MB)          Memory (GB)    
--------------------------------------------------------------------------------
login-app-544d5c5674-c4bc5              85.60                0.084          
login-app-544d5c5674-w9qdj              82.30                0.080          
login-app-544d5c5674-xwljs              88.90                0.087          
--------------------------------------------------------------------------------
TOTAL                                    256.80               0.251          

🌐 Network Statistics:
  Network Receive:
  Pod Name                                Bytes/s         KB/s            MB/s           
  ------------------------------------------------------------------------------
  login-app-544d5c5674-c4bc5             1250.5          1.22            0.001          

  Network Transmit:
  Pod Name                                Bytes/s         KB/s            MB/s           
  ------------------------------------------------------------------------------
  login-app-544d5c5674-c4bc5             3500.8          3.42            0.003          
```

### Programmatic Integration

You can also import the monitor class in your own Python scripts:

```python
from prometheus_monitor import PrometheusMonitor

# Initialize monitor
monitor = PrometheusMonitor(prometheus_url="http://localhost:9090")

# Get CPU metrics
cpu_metrics = monitor.get_cpu_usage()
for metric in cpu_metrics:
    print(f"Pod: {metric['pod']}, CPU: {metric['cpu_millicores']} millicores")

# Get memory metrics
memory_metrics = monitor.get_memory_usage()
for metric in memory_metrics:
    print(f"Pod: {metric['pod']}, Memory: {metric['memory_mb']} MB")

# Export to JSON
monitor.export_to_json("my_metrics.json")
```

## Troubleshooting

### Metrics Server Issues

```bash
# Check metrics-server logs
kubectl logs -n kube-system -l k8s-app=metrics-server

# Verify the API service
kubectl get apiservice v1beta1.metrics.k8s.io -o yaml

# Restart metrics-server if needed
kubectl rollout restart deployment metrics-server -n kube-system
```

### Prometheus Issues

```bash
# Check Prometheus pods
kubectl get pods -n monitoring | grep prometheus

# Check Prometheus logs
kubectl logs -n monitoring -l app=prometheus

# Check targets in Prometheus UI
# Port-forward Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090
# Then access http://localhost:9090/targets in your browser
```

### Grafana Issues

```bash
# Reset admin password if needed
kubectl exec -it -n monitoring $(kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}') -- grafana-cli admin reset-admin-password admin
```

This comprehensive monitoring setup will provide you with the metrics needed to make informed autoscaling decisions and gain insights into your application's performance.

Similar code found with 2 license types