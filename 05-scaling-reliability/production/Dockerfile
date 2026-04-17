FROM python:3.11-slim

WORKDIR /app

# Keep dependencies explicit here because this exercise folder does not ship requirements.txt.
RUN pip install --no-cache-dir fastapi uvicorn redis pydantic

COPY app.py /app/app.py
COPY utils /app/utils

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
