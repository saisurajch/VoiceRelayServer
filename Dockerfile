FROM python:3.11-slim
WORKDIR /app
COPY main.py .
EXPOSE 5500
CMD ["python", "main.py"]