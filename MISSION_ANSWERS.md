# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. API key bị hardcode trực tiếp trong mã nguồn, nên rất dễ bị lộ nếu đẩy lên GitHub.
2. Thông tin kết nối cơ sở dữ liệu cũng bị viết cứng, bao gồm cả mật khẩu, gây rủi ro bảo mật cao.
3. Ứng dụng dùng host cố định là `localhost`, nên không thể chạy đúng trong môi trường cloud như Railway hay Render.
4. Port bị cố định là `8000` thay vì đọc từ biến môi trường `PORT`, nên thiếu tính linh hoạt khi triển khai.
5. Bật `reload=True` trong `uvicorn.run()`, đây là chế độ dành cho phát triển, không phù hợp với production.
6. Không có health check endpoint, nên nền tảng triển khai khó kiểm tra trạng thái sống/chết của ứng dụng.
7. Không có xử lý graceful shutdown hoặc cơ chế dọn dẹp tài nguyên khi ứng dụng tắt.

### Exercise 1.2: Environment differences
1. Bản develop có thể chạy được trên máy cá nhân (localhost), nhưng chưa sẵn sàng cho production vì thiếu các tiêu chí vận hành quan trọng như health/readiness check, quản lý cấu hình qua biến môi trường, logging chuẩn và xử lý tắt dịch vụ an toàn.
2. Bản production được thiết kế để triển khai thật: bind `0.0.0.0`, đọc `PORT`/config từ environment, có endpoint `/health` và `/ready`, hạn chế log nhạy cảm, có lifecycle startup-shutdown; vì vậy ổn định hơn, an toàn hơn và tương thích với cloud platform.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config  | Giá trị cấu hình bị hardcode trong code (host, port, key, DB URL) | Đọc cấu hình từ environment thông qua `settings` | Dễ thay đổi theo từng môi trường, tránh sửa mã nguồn khi deploy và giảm lỗi cấu hình |
| Logging | Dùng `print`, log thô và không có cấu trúc | Dùng `logging` dạng JSON có level rõ ràng | Dễ giám sát, tìm lỗi nhanh và tích hợp với hệ thống log tập trung |
| Debug   | `reload=True`, `DEBUG=True`, host `localhost` | `reload` theo `settings.debug`, host/port theo env (phù hợp cloud) | Tránh rò rỉ thông tin, tăng ổn định và chạy đúng trên container/platform |
| Secrets | API key và thông tin DB xuất hiện trực tiếp trong code, thậm chí bị in ra log | Secrets lấy từ biến môi trường, không log giá trị nhạy cảm | Bảo mật tốt hơn, tránh lộ credential trên GitHub và trong log hệ thống |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: `python:3.11`.
2. Working directory: `/app` (được thiết lập bằng `WORKDIR /app`).
3. Tại sao `COPY requirements.txt` trước: để tận dụng Docker layer cache. Khi code thay đổi nhưng dependencies không đổi, Docker không cần cài lại toàn bộ thư viện, giúp build nhanh hơn.
4. `CMD` vs `ENTRYPOINT`: `CMD` là lệnh mặc định có thể bị ghi đè dễ dàng khi chạy container; `ENTRYPOINT` định nghĩa lệnh chính của container (khó bị thay thế hơn, thường chỉ truyền thêm tham số). Trong file này đang dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Container behavior
1. Image develop sử dụng `python:3.11` (full distribution), tất cả code và dependencies đều nằm trong một layer → image lớn nhưng đơn giản.
2. Image production sử dụng `python:3.11-slim` (nhẹ hơn) với multi-stage build: stage 1 (builder) cài dependencies với build tools; stage 2 (runtime) chỉ copy packages đã cài, code và non-root user → image nhỏ, an toàn hơn.

### Exercise 2.3: Image size comparison
- Develop: 1150 MB (1.15 GB)
- Production: 160 MB (do multi-stage + slim base image)
- Difference: ~90% nhỏ hơn (production nhẹ hơn khoảng 1000 MB)

## Exercise 2.4: Docker Compose stack

### Services được start:
1. **Agent** (FastAPI) — AI Agent service chạy trên port 8000
2. **Redis** (v7-alpine) — Cache & session storage (port 6379)
3. **Qdrant** (v1.9.0) — Vector database cho RAG (port 6333)
4. **Nginx** (alpine) — Reverse proxy & load balancer (port 80/443)

### Architecture Diagram:
```
Client (HTTP:80)
    ↓
Nginx (Reverse Proxy)
    ↓
Agent (FastAPI) ↔ Redis (Cache/Session)
    ↓
Qdrant (Vector DB)
```

### Cách chúng communicate:
- **Client → Nginx**: HTTP request đi vào port 80, Nginx route đến Agent
- **Nginx → Agent**: Load balance requests giữa các Agent instances, health check Agent
- **Agent ↔ Redis**: Agent lưu session, cache vào Redis qua `REDIS_URL=redis://redis:6379/0`
- **Agent ↔ Qdrant**: Agent query vectors cho RAG qua `QDRANT_URL=http://qdrant:6333`
- **Tất cả services**: Chạy trong cùng Docker network `internal`, có thể gọi nhau bằng service name (DNS)
- **Health checks**: Nginx định kỳ kiểm tra Agent bằng `/health` endpoint, Redis & Qdrant cũng có health check để service_healthy condition

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://agent-production-a5a7.up.railway.app
- Screenshot: [Service running](screenshots/running.jpg)

## Part 4: API Security

### Exercise 4.1-4.3: Test results
#### Exercise 4.1: API key flow (from app.py)
1. API key được check trong dependency `verify_api_key()` của endpoint `/ask`, thông qua header `X-API-Key` (khai báo bằng `APIKeyHeader(name="X-API-Key", auto_error=False)`).
2. Nếu sai key:
    - Thiếu key: trả về `401` với message yêu cầu gửi header `X-API-Key`.
    - Key không đúng: trả về `403` với message `Invalid API key.`
3. Rotate key: đổi giá trị biến môi trường `AGENT_API_KEY` trên server/container, rồi restart service để app nạp key mới. Để không gián đoạn, có thể áp dụng chiến lược overlap ngắn hạn (chấp nhận cả key cũ và key mới trong thời gian chuyển đổi), sau đó thu hồi key cũ.

#### Exercise 4.2: JWT authentication
[JWT Authentication Output](screenshots/jwt_auth.jpg)

#### Exercise 4.3: Rate limiting
1. **Algorithm được dùng:** Sliding Window Counter (cài bằng `deque` timestamps theo từng user). Mỗi request sẽ xóa các timestamp cũ ngoài cửa sổ 60 giây, rồi kiểm tra số request còn trong window.
2. **Limit requests/minute:**
    - User thường: `10 requests / 60s` (`rate_limiter_user = RateLimiter(max_requests=10, window_seconds=60)`)
    - Admin: `100 requests / 60s` (`rate_limiter_admin = RateLimiter(max_requests=100, window_seconds=60)`)
3. **Bypass limit cho admin:** Không phải bỏ hẳn rate limit, mà dùng tier cao hơn. Trong `app.py`, nếu `role == "admin"` thì chọn `rate_limiter_admin`; ngược lại dùng `rate_limiter_user`.

### Exercise 4.4: Cost guard implementation
1. Cost guard được đặt ngay trước bước gọi LLM trong endpoint `/ask` để chặn request nếu user hoặc hệ thống đã gần/vượt budget, tránh phát sinh thêm chi phí không cần thiết.
2. Mỗi request sẽ gọi `cost_guard.check_budget(username)` để kiểm tra 2 lớp giới hạn: budget theo user mỗi ngày (`$1/day`) và budget tổng của service (`$10/day`). Nếu vượt ngưỡng, API trả `402` cho user hoặc `503` khi toàn hệ thống hết budget.
3. Sau khi nhận response từ LLM, hệ thống ước lượng token usage từ input/output, rồi gọi `cost_guard.record_usage(...)` để cộng dồn số request, token đã dùng và tổng cost. Khi user chạm khoảng `80%` budget thì hệ thống chỉ log cảnh báo để theo dõi sớm.
4. Thiết kế này phù hợp cho demo vì đơn giản và dễ hiểu; nếu đưa vào production thật thì nên thay phần lưu in-memory bằng Redis/DB để budget không bị mất khi restart service.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks
Đã implement 2 endpoint trong bản develop/production theo đúng vai trò liveness và readiness:

1. `/health` (liveness)
- Trả về HTTP `200` khi process đang sống.
- Response có `status`, `instance_id`, `uptime_seconds` để tiện quan sát khi scale.

2. `/ready` (readiness)
- Thực hiện kiểm tra dependency quan trọng (Redis ping).
- Trả về HTTP `200` khi sẵn sàng nhận traffic.
- Trả về HTTP `503` nếu dependency chưa sẵn sàng.

Kết quả test:
- `GET http://localhost:8080/health` trả `200 OK`.
- Trong output có `redis_connected: true`, xác nhận backend dependency đã ready.

### Exercise 5.2: Graceful shutdown
Đã triển khai cơ chế graceful shutdown theo lifecycle server:

1. Khi nhận tín hiệu dừng, instance ngừng nhận request mới.
2. Các request đang xử lý được hoàn tất trong timeout cho phép.
3. Kết nối tài nguyên được đóng khi app shutdown.
4. Process thoát có kiểm soát, không cắt ngang request.

Ý nghĩa:
- Giảm lỗi 5xx khi rolling update/restart container.
- Giữ trải nghiệm ổn định cho client trong lúc deploy.

### Exercise 5.3: Stateless design
Đã refactor theo đúng yêu cầu stateless:

1. Không lưu state hội thoại trong biến memory theo instance.
2. Lưu/đọc history từ Redis với key theo user/session (`history:{user_id}` và session key).
3. Redis được cấu hình là bắt buộc ở startup (fail-fast nếu Redis không sẵn sàng).

### Exercise 5.4: Load balancing
Đã chạy stack với Nginx + 3 agent instances:

1. Lệnh chạy:
    `docker compose up -d --build --scale agent=3`
2. Trạng thái services:
    `production-agent-1`, `production-agent-2`, `production-agent-3` đều `Up (healthy)`.
3. Nginx publish `0.0.0.0:8080->80/tcp` và route request vào cụm agent.

Kết quả quan sát:
- Header và output test cho thấy request được phân tán sang nhiều backend khác nhau.
- Hệ thống vẫn phục vụ bình thường khi chạy theo mô hình nhiều instance sau load balancer.

### Exercise 5.5: Test stateless
Đã chạy thành công script:

`python test_stateless.py`

Kết quả chính:

1. Script tạo session và gửi 5 request liên tiếp.
2. Request được phục vụ bởi nhiều instance khác nhau:
    `instance-57d05d`, `instance-9bbfe1`, `instance-9bd648`.
3. Conversation history vẫn toàn vẹn:
    `Total messages: 10` (5 user + 5 assistant).
4. Script kết luận:
    `Session history preserved across all instances via Redis`.
