# Deployment Information

## Public URL
https://agent-production-a5a7.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://agent-production-a5a7.up.railway.app/health
# Expected: {"status":"ok", ...}
```

### Service Root Check
```bash
curl https://agent-production-a5a7.up.railway.app/
# Expected: service info JSON
```

### API Test (with authentication)
```bash
curl -X POST https://agent-production-a5a7.up.railway.app/ask \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: 200 OK + answer JSON
```

### Authentication Required Test
```bash
curl -X POST https://agent-production-a5a7.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: 401 Unauthorized
```

### Rate Limiting Test
```bash
for i in {1..15}; do
  curl -X POST https://agent-production-a5a7.up.railway.app/ask \
    -H "X-API-Key: secret-key-123" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"test","question":"rate test"}'
  echo ""
done
# Expected: eventually returns 429 Too Many Requests
```

## Environment Variables Set
- PORT
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL
- RATE_LIMIT_PER_MINUTE
- MONTHLY_BUDGET_USD

## Screenshots
- [Deployment dashboard](screenshots/dashboard.jpg)
- [Service running](screenshots/running.jpg)
- [Test results](screenshots/test.jpg)
