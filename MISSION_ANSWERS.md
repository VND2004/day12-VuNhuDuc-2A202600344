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
- URL: https://your-app.railway.app
- Screenshot: [Link to screenshot in repo]

### Exercise 3.2: Deployment notes
1. [Your answer]
2. [Your answer]

## Part 4: API Security

### Exercise 4.1-4.3: Test results
[Paste your test outputs]

### Exercise 4.4: Cost guard implementation
[Explain your approach]

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
[Your explanations and test results]

## Additional Notes

- [Optional note 1]
- [Optional note 2]