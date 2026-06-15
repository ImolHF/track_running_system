FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn[standard]==0.34.0 \
    sqlalchemy==2.0.36 \
    jinja2==3.1.4 \
    python-multipart==0.0.19 \
    bcrypt==4.0.1 \
    cryptography==44.0.1 \
    garth==0.8.0 \
    apscheduler==3.11.2 \
    python-dotenv==1.0.1 \
    aiofiles==24.1.0 \
    itsdangerous==2.2.0

ENV HOST=0.0.0.0
ENV PORT=8000

RUN mkdir -p /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
