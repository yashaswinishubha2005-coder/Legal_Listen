FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN pip install --no-cache-dir -e . && test -f models/legallisten_nlu.joblib || python -m legallisten.nlu.train
EXPOSE 8000
CMD ["uvicorn", "legallisten.app:app", "--host", "0.0.0.0", "--port", "8000"]
