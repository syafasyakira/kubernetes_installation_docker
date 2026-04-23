# Load Balancing and Autoscaling for Login Web Application

This guide sets up NGINX Ingress Controller as a load balancer and configures Horizontal Pod Autoscaling (HPA) for the login-app.

## Cluster Information

| Item | Value |
|------|-------|
| Master node | kube-master (10.34.7.115) |
| Worker node | k8s-control (10.34.7.5) |
| App NodePort | 30080 |
| Ingress (LB) port | 30081 |
| HPA min/max replicas | 2 / 4 |
| CPU scale-up threshold | 80% |

---

## Prerequisites Check

Before starting, verify the cluster is healthy:

```bash
# Check nodes
kubectl get nodes

# Check login-app is running
kubectl get pods -l app=login-app

# Check current service
kubectl get svc login-app

# Check if HPA already exists
kubectl get hpa login-app-hpa
```

Expected: 2+ login-app pods Running, service type NodePort on port 30080.

---

## Step 1 — Install NGINX Ingress Controller

> Skip this step if `kubectl get pods -n ingress-nginx` already shows running pods.

```bash
# Add Helm repo
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install NGINX ingress on the worker node (k8s-control), expose on NodePort 30081
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.nodeSelector."kubernetes\.io/hostname"=k8s-control \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30081

# Wait for the ingress controller pod to be ready (up to 2 min)
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Confirm it is running
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx
```

---

## Step 2 — Apply Ingress Resource

The ingress resource routes all HTTP traffic through the NGINX controller to the login-app service.

```bash
# Apply from the existing file in this repository
kubectl apply -f k8s-login-app/k8s/login-app-ingress.yaml

# Verify ingress is created
kubectl get ingress
kubectl describe ingress login-app-ingress
```

The `login-app-ingress.yaml` content:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: login-app-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: login-app
            port:
              number: 80
```

---

## Step 3 — Scale Up login-app Replicas

For proper load balancing, run at least 3 replicas:

```bash
kubectl scale deployment login-app --replicas=3

# Wait until all replicas are ready
kubectl rollout status deployment login-app

# Confirm 3 pods are running
kubectl get pods -l app=login-app -o wide
```

---

## Step 4 — Apply HPA for Autoscaling

> Skip this step if `kubectl get hpa login-app-hpa` already shows an HPA.

```bash
# Apply from the existing file in this repository
kubectl apply -f k8s-login-app/k8s/login-app-hpa.yaml

# Verify HPA is active
kubectl get hpa login-app-hpa
kubectl describe hpa login-app-hpa
```

The `login-app-hpa.yaml` content:

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
  maxReplicas: 4
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
      - type: Pods
        value: 1
        periodSeconds: 60
      selectPolicy: Min
```

---

## Step 5 — Access the Application

After setup, the login-app is accessible via two routes:

| Route | URL | Description |
|-------|-----|-------------|
| Direct NodePort | http://10.34.7.115:30080 | Bypasses ingress |
| Via NGINX Ingress (LB) | http://10.34.7.115:30081 | Goes through load balancer |
| Via Worker Node | http://10.34.7.5:30081 | Worker node access |

Login credentials: **admin / admin123**

---

## Step 6 — Add Pod Identity Header (Optional but Recommended)

By default, the backend does not reveal which pod handled a request. Adding an `X-Served-By` header lets you verify load distribution with `curl`.

The following line is already added to `k8s-login-app/app/server.js`:

```js
app.use((req, res, next) => {
  res.set('X-Served-By', process.env.HOSTNAME || 'unknown');
  next();
});
```

`HOSTNAME` is automatically set to the pod name by Kubernetes.

After this change, rebuild and redeploy the image:

```bash
# 1. SSH into the worker node (where pods run)
ssh widhi@10.34.7.5

# 2. On the worker node — build new image
cd /path/to/kubernetes_installation_docker/k8s-login-app/app
sudo docker build -t login-app:latest .

# 3. Exit back to master node
exit

# 4. On the master node — rollout restart to pick up the new image
kubectl rollout restart deployment login-app
kubectl rollout status deployment login-app
```

---

## Step 7 — Test Load Balancing

Verify that requests are distributed across all pods:

```bash
# Check which pods exist and their IPs
kubectl get pods -l app=login-app -o wide

# Send 10 requests via the ingress and observe X-Served-By header
for i in {1..10}; do
  echo -n "Request $i: "
  curl -si http://10.34.7.115:30081/ | grep -i "x-served-by"
  sleep 0.5
done

# Watch pod request counts in real time (open separate terminal)
kubectl logs -f -l app=login-app --prefix=true | grep "GET\|POST"
```

You should see different pod names in the `X-Served-By` header across requests, confirming load balancing is working.

Example output:
```
Request 1: X-Served-By: login-app-7d6f9b8c4-abc12
Request 2: X-Served-By: login-app-7d6f9b8c4-xyz99
Request 3: X-Served-By: login-app-7d6f9b8c4-abc12
```

---

## Step 8 — Test Autoscaling

Trigger CPU load to verify HPA scales pods up automatically:

```bash
# Watch HPA status in a separate terminal
watch kubectl get hpa login-app-hpa

# Watch pods scaling in another terminal
watch kubectl get pods -l app=login-app

# Generate load using a busybox pod (runs for ~3 minutes)
kubectl run load-gen --image=busybox --restart=Never --rm -it -- \
  sh -c "while true; do wget -q -O- http://login-app/; done"
```

Expected behavior:
- CPU % will rise above 80%
- HPA scales up from 2 → 4 pods (within ~60s)
- After stopping load, pods scale back down after ~300s stabilization window

```bash
# Stop the load generator (Ctrl+C), then monitor scale-down
kubectl get hpa login-app-hpa -w
kubectl get pods -l app=login-app -w
```

---

## Monitoring

```bash
# Live HPA metrics
kubectl get hpa login-app-hpa

# Current CPU/memory usage of login-app pods
kubectl top pods -l app=login-app

# HPA events and decisions
kubectl describe hpa login-app-hpa

# Ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=50

# Ingress resource details
kubectl describe ingress login-app-ingress
```

---

## Troubleshooting

### App returns "Database error" after restart
```bash
kubectl rollout restart deployment login-app
kubectl rollout status deployment login-app
```

### Ingress returns 404 or 502
```bash
# Check ingress controller is running
kubectl get pods -n ingress-nginx

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=30

# Check ingress routing
kubectl describe ingress login-app-ingress

# Check login-app endpoints are registered
kubectl get endpoints login-app
```

### HPA shows "unknown" metrics
```bash
# Ensure metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Test metrics collection
kubectl top pods -l app=login-app

# Restart metrics-server if needed
kubectl rollout restart deployment metrics-server -n kube-system
```

### Ingress port 30081 not accessible
```bash
# Verify NodePort is bound to 30081
kubectl get svc -n ingress-nginx

# Confirm the firewall allows port 30081
# On the node: sudo ufw allow 30081/tcp
```

---

## Summary

| Component | Status Command | Expected |
|-----------|---------------|----------|
| login-app pods | `kubectl get pods -l app=login-app` | 2-4 Running |
| login-app service | `kubectl get svc login-app` | NodePort 30080 |
| NGINX ingress controller | `kubectl get pods -n ingress-nginx` | Running |
| Ingress resource | `kubectl get ingress` | login-app-ingress |
| HPA | `kubectl get hpa login-app-hpa` | Targets shown, min 2 max 4 |
| Metrics server | `kubectl top pods -l app=login-app` | CPU/memory values shown |

