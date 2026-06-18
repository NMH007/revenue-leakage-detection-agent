# Container image for Hugging Face Spaces (Docker SDK).
# HF Spaces expose port 7860 by default, so we run gunicorn there.
FROM python:3.12-slim

# HF runs containers as a non-root user (uid 1000). Create it and use it.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

EXPOSE 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
