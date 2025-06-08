# Notification Engine Deployment Guide

## Overview

The IntelliBrowse Notification Engine is a comprehensive multi-channel notification system designed for production deployment. This guide covers deployment configuration, environment setup, monitoring, and operational procedures.

## Architecture Summary

### Components
- **Notification Controller**: HTTP API orchestration layer
- **Service Layer**: Business logic and notification processing
- **Delivery Daemon**: Background notification delivery engine
- **Channel Adapters**: Email, WebSocket, and webhook delivery
- **Health Monitoring**: Comprehensive observability and metrics

### Technology Stack
- **Framework**: FastAPI with async/await
- **Database**: MongoDB with Motor async client
- **Authentication**: JWT-based security
- **Background Processing**: Python asyncio with delivery daemon
- **Monitoring**: Health checks and performance metrics

## Environment Configuration

### Required Environment Variables

```bash
# Database Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=intellibrowse

# Authentication
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Notification Engine Configuration
NOTIFICATION_DAEMON_ENABLED=true
NOTIFICATION_DAEMON_WORKERS=5
NOTIFICATION_DAEMON_BATCH_SIZE=50
NOTIFICATION_DAEMON_HEALTH_CHECK_INTERVAL=30

# Email Configuration (SendGrid Primary)
SENDGRID_API_KEY=your-sendgrid-api-key
SENDGRID_FROM_EMAIL=notifications@yourdomain.com
SENDGRID_FROM_NAME="IntelliBrowse Notifications"

# Email Configuration (Amazon SES Fallback)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
SES_FROM_EMAIL=notifications@yourdomain.com

# WebSocket Configuration
WEBSOCKET_MAX_CONNECTIONS=1000
WEBSOCKET_HEARTBEAT_INTERVAL=30
WEBSOCKET_CONNECTION_TIMEOUT=300

# Webhook Configuration
WEBHOOK_TIMEOUT_SECONDS=30
WEBHOOK_MAX_RETRIES=3
WEBHOOK_RETRY_DELAY_SECONDS=5

# Performance Configuration
NOTIFICATION_QUEUE_SIZE=1000
NOTIFICATION_PROCESSING_TIMEOUT=300
NOTIFICATION_RETRY_MAX_ATTEMPTS=3
NOTIFICATION_RETRY_DELAY_SECONDS=60

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/intellibrowse/notifications.log

# Health Monitoring
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_INTERVAL=60
METRICS_COLLECTION_ENABLED=true
METRICS_RETENTION_DAYS=30
```

### Development Environment

```bash
# Development-specific settings
ENVIRONMENT=development
DEBUG=true
CORS_ENABLED=true
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]

# Database (Development)
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=intellibrowse_dev

# Email (Development - Use test providers)
EMAIL_PROVIDER=console  # Logs emails to console instead of sending
SENDGRID_API_KEY=test-key

# Reduced timeouts for development
NOTIFICATION_PROCESSING_TIMEOUT=60
WEBHOOK_TIMEOUT_SECONDS=10
```

### Production Environment

```bash
# Production-specific settings
ENVIRONMENT=production
DEBUG=false
CORS_ENABLED=true
CORS_ORIGINS=["https://yourdomain.com", "https://app.yourdomain.com"]

# Database (Production)
MONGODB_URL=mongodb://mongo-cluster:27017/intellibrowse?replicaSet=rs0
MONGODB_DATABASE=intellibrowse_prod

# Security (Production)
JWT_SECRET_KEY=your-production-secret-key-256-bits
TRUSTED_HOSTS=["yourdomain.com", "*.yourdomain.com"]

# Performance (Production)
NOTIFICATION_DAEMON_WORKERS=10
NOTIFICATION_QUEUE_SIZE=5000
WEBSOCKET_MAX_CONNECTIONS=5000

# Monitoring (Production)
HEALTH_CHECK_ENABLED=true
METRICS_COLLECTION_ENABLED=true
STRUCTURED_LOGGING=true
```

## Deployment Methods

### Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY .env .env

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  intellibrowse-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URL=mongodb://mongo:27017
      - MONGODB_DATABASE=intellibrowse
    depends_on:
      - mongo
      - redis
    volumes:
      - ./logs:/var/log/intellibrowse
    restart: unless-stopped

  mongo:
    image: mongo:6.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - intellibrowse-api
    restart: unless-stopped

volumes:
  mongo_data:
```

### Kubernetes Deployment

#### Deployment YAML
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: intellibrowse-notification-engine
  labels:
    app: intellibrowse
    component: notification-engine
spec:
  replicas: 3
  selector:
    matchLabels:
      app: intellibrowse
      component: notification-engine
  template:
    metadata:
      labels:
        app: intellibrowse
        component: notification-engine
    spec:
      containers:
      - name: notification-engine
        image: intellibrowse/notification-engine:latest
        ports:
        - containerPort: 8000
        env:
        - name: MONGODB_URL
          valueFrom:
            secretKeyRef:
              name: intellibrowse-secrets
              key: mongodb-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: intellibrowse-secrets
              key: jwt-secret
        - name: SENDGRID_API_KEY
          valueFrom:
            secretKeyRef:
              name: intellibrowse-secrets
              key: sendgrid-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/notifications/health/status
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: intellibrowse-notification-service
spec:
  selector:
    app: intellibrowse
    component: notification-engine
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

## Database Setup

### MongoDB Configuration

#### Indexes Creation
```javascript
// Notification collection indexes
db.notifications.createIndex({ "user_id": 1, "created_at": -1 })
db.notifications.createIndex({ "status": 1, "created_at": -1 })
db.notifications.createIndex({ "notification_type": 1, "created_at": -1 })
db.notifications.createIndex({ "priority": 1, "status": 1 })

// Notification history indexes
db.notification_history.createIndex({ "user_id": 1, "timestamp": -1 })
db.notification_history.createIndex({ "notification_id": 1 })
db.notification_history.createIndex({ "delivery_status": 1, "timestamp": -1 })

// User preferences indexes
db.notification_preferences.createIndex({ "user_id": 1 }, { unique: true })
db.notification_preferences.createIndex({ "updated_at": -1 })

// Audit logs indexes
db.notification_audit_logs.createIndex({ "timestamp": -1 })
db.notification_audit_logs.createIndex({ "user_id": 1, "timestamp": -1 })
db.notification_audit_logs.createIndex({ "action": 1, "timestamp": -1 })
```

#### Replica Set Configuration (Production)
```javascript
// Initialize replica set
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo-1:27017" },
    { _id: 1, host: "mongo-2:27017" },
    { _id: 2, host: "mongo-3:27017" }
  ]
})
```

## Monitoring and Observability

### Health Check Endpoints

| Endpoint | Purpose | Response Time Target |
|----------|---------|---------------------|
| `/health` | Basic service health | < 100ms |
| `/api/v1/notifications/health/status` | Comprehensive health status | < 500ms |
| `/api/v1/notifications/health/metrics` | Performance metrics | < 1000ms |
| `/api/v1/notifications/health/daemon` | Delivery daemon status | < 200ms |
| `/api/v1/notifications/health/channels` | Channel adapter status | < 300ms |

### Metrics Collection

#### Key Performance Indicators (KPIs)
- **Delivery Success Rate**: Target > 99%
- **Average Delivery Time**: Target < 500ms (in-app), < 30s (email)
- **Queue Processing Rate**: Target > 100 notifications/minute
- **Error Rate**: Target < 1%
- **System Uptime**: Target > 99.9%

#### Prometheus Metrics (if using Prometheus)
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'intellibrowse-notifications'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/notifications/health/metrics'
    scrape_interval: 30s
```

### Logging Configuration

#### Structured Logging Format
```json
{
  "timestamp": "2025-01-06T20:00:00Z",
  "level": "INFO",
  "service": "notification-engine",
  "component": "delivery-daemon",
  "request_id": "req_abc123",
  "user_id": "user_456",
  "notification_id": "ntfy_789def",
  "message": "Notification delivered successfully",
  "metadata": {
    "channel": "email",
    "delivery_time_ms": 2500,
    "retry_count": 0
  }
}
```

#### Log Aggregation (ELK Stack)
```yaml
# logstash.conf
input {
  file {
    path => "/var/log/intellibrowse/notifications.log"
    codec => json
  }
}

filter {
  if [service] == "notification-engine" {
    mutate {
      add_tag => ["notification"]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "intellibrowse-notifications-%{+YYYY.MM.dd}"
  }
}
```

## Security Configuration

### Authentication and Authorization
- JWT-based authentication for all protected endpoints
- Role-based access control for admin functions
- API rate limiting to prevent abuse
- Input validation and sanitization

### Network Security
- HTTPS/TLS encryption for all communications
- Firewall rules to restrict database access
- VPN or private network for internal communications
- Regular security updates and patches

### Data Protection
- Encryption at rest for sensitive data
- Secure credential management (AWS Secrets Manager, HashiCorp Vault)
- Data retention policies and automated cleanup
- GDPR compliance for user data handling

## Performance Tuning

### Application Level
```python
# Performance configuration
NOTIFICATION_DAEMON_WORKERS = 10  # Adjust based on CPU cores
NOTIFICATION_QUEUE_SIZE = 5000    # Adjust based on memory
WEBSOCKET_MAX_CONNECTIONS = 5000  # Adjust based on requirements
DATABASE_CONNECTION_POOL_SIZE = 20 # Adjust based on load
```

### Database Level
- Connection pooling and optimization
- Index optimization for query performance
- Read replicas for analytics queries
- Sharding for high-volume deployments

### Infrastructure Level
- Load balancing across multiple instances
- Auto-scaling based on CPU/memory usage
- CDN for static assets
- Caching layer (Redis) for frequently accessed data

## Backup and Recovery

### Database Backup
```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
mongodump --uri="mongodb://localhost:27017/intellibrowse" --out="/backups/mongo_$DATE"
tar -czf "/backups/mongo_$DATE.tar.gz" "/backups/mongo_$DATE"
rm -rf "/backups/mongo_$DATE"

# Retain backups for 30 days
find /backups -name "mongo_*.tar.gz" -mtime +30 -delete
```

### Application Backup
- Configuration files backup
- SSL certificates backup
- Log files archival
- Disaster recovery procedures

## Troubleshooting

### Common Issues

#### High Memory Usage
```bash
# Check memory usage
docker stats intellibrowse-api

# Adjust memory limits
docker run --memory=1g intellibrowse/notification-engine
```

#### Database Connection Issues
```bash
# Check MongoDB connectivity
mongosh --eval "db.adminCommand('ping')"

# Check connection pool status
curl http://localhost:8000/api/v1/notifications/health/status
```

#### Email Delivery Failures
```bash
# Check SendGrid API status
curl -H "Authorization: Bearer $SENDGRID_API_KEY" \
     https://api.sendgrid.com/v3/user/account

# Check email adapter health
curl http://localhost:8000/api/v1/notifications/health/channels
```

### Log Analysis
```bash
# Search for errors in logs
grep "ERROR" /var/log/intellibrowse/notifications.log

# Monitor real-time logs
tail -f /var/log/intellibrowse/notifications.log | grep "notification_id"

# Analyze delivery performance
grep "delivered successfully" /var/log/intellibrowse/notifications.log | \
  jq '.metadata.delivery_time_ms' | \
  awk '{sum+=$1; count++} END {print "Average delivery time:", sum/count, "ms"}'
```

## Maintenance Procedures

### Regular Maintenance
- Weekly health check review
- Monthly performance analysis
- Quarterly security audit
- Annual disaster recovery testing

### Updates and Upgrades
- Blue-green deployment strategy
- Database migration procedures
- Configuration rollback procedures
- Service dependency updates

### Monitoring Alerts
- Service downtime alerts
- High error rate alerts
- Performance degradation alerts
- Security incident alerts

## Support and Documentation

### API Documentation
- OpenAPI/Swagger documentation available at `/docs`
- Comprehensive endpoint documentation
- Example requests and responses
- Authentication requirements

### Operational Runbooks
- Incident response procedures
- Escalation procedures
- Contact information
- Service level agreements

---

**Deployment Status**: Ready for production deployment  
**Last Updated**: 2025-01-06  
**Version**: 1.0.0  
**Support Contact**: DevOps Team 