FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /app
COPY app.py recurring.py ./
COPY static ./static
RUN chmod -R a=rX /app && mkdir /data && chown 65532:65532 /data
USER 65532:65532
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 REFERENCE_DB=/data/reference.sqlite3
EXPOSE 8088
CMD ["python","app.py"]
