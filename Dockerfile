FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv libreoffice-writer fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/prompt-python \
    && /opt/prompt-python/bin/pip install --no-cache-dir PyMuPDF==1.26.6
WORKDIR /app
COPY manifest.webmanifest prompt-icon-*.png show-state.js prompt-copy.cjs index.html build-speaker-index.py entrypoint.sh ./
RUN chmod 755 /app/entrypoint.sh && mkdir /app/data && chown node:node /app/data
USER node
ENV PORT=3000 BIND=0.0.0.0 PAGE_DIRECTORY=/tmp/prompt-pages
EXPOSE 3000
ENTRYPOINT ["/app/entrypoint.sh"]
