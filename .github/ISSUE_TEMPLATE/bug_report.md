---
name: Bug Report
about: Create a detailed bug report to help us improve the Data Processing Pipeline
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
### Summary
<!-- Provide a clear and concise description of the bug (minimum 30 characters) -->

### Component
<!-- Select the affected component -->
- [ ] API Gateway
- [ ] Task Processing
- [ ] OCR Engine
- [ ] Web Scraping
- [ ] Storage System
- [ ] Security
- [ ] Monitoring

### Error Code
<!-- If applicable, provide the system error code (ERR-001 to ERR-006) -->

### Severity
<!-- Select one severity level -->
- [ ] Critical - System down (1h response)
- [ ] High - Major impact (4h response)
- [ ] Medium - Limited impact (24h response)
- [ ] Low - Minor issues (72h response)

## Environment
### Environment Type
<!-- Select the environment where the bug occurred -->
- [ ] Development
- [ ] Staging
- [ ] Production

### Version Information
<!-- Provide the system version or commit hash -->
Version/Commit: 

## Reproduction Steps
### Prerequisites
<!-- List any required setup or conditions needed to reproduce the bug -->

### Steps to Reproduce
<!-- Provide detailed step-by-step instructions (minimum 2 steps required) -->
1. 
2. 
3. 

## Expected vs Actual Behavior
### Expected Behavior
<!-- Describe what should happen -->

### Actual Behavior
<!-- Describe what actually happens -->

## System Information
### Error Logs
<!-- Include relevant error logs or stack traces -->
```
<!-- Paste logs here -->
```

### System Metrics
<!-- Provide relevant performance metrics at the time of the error -->
- API Latency (ms): 
- CPU Usage (%): 
- Memory Usage (MB): 
- Error Rate (%): 

## Additional Context
<!-- Add any other relevant context about the problem here -->

---
<!-- Do not modify below this line -->
**For Internal Use:**
- Issue routing will be automatically handled based on the error code:
  - API Errors (ERR-001): @api-team
  - Task Failures (ERR-002, ERR-003): @task-processing-team
  - Storage Errors (ERR-004): @storage-team
  - OCR Errors (ERR-005): @ocr-team
  - Scraping Errors (ERR-006): @scraping-team