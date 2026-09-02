# The service drives browsers in Solari's cloud, not here: solari.launch()
# connects to a remote endpoint over a websocket. So this image needs the
# patchright client and its Node driver, and no browser at all -- which is the
# difference between ~180MB and well over a gigabyte.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    FARE_DB=/data/cache.db

WORKDIR /app

# Only what the service imports. The dev tools' extras (Pillow, a local
# browser) are not installed: nothing here records a demo or screenshots a page.
RUN pip install --no-cache-dir "solari-browser>=0.1.2" "patchright>=1.40"

COPY *.py ./
COPY *.html ./

# The cache lives on a mounted volume where there is one, and survives a
# restart. Without it every redeploy would re-search everything people had
# already asked for, at real cost.
VOLUME ["/data"]
EXPOSE 8080

# A container with no key would start, serve the page, and fail every search
# with something unhelpful. Fail here instead, where the message is read.
CMD ["sh", "-c", "test -n \"$SOLARI_API_KEY\" || { echo 'SOLARI_API_KEY is not set'; exit 1; }; exec python server.py"]
