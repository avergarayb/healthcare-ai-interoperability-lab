FROM alpine:3.22.1
RUN apk add --no-cache socat \
    && adduser -D -H -u 65532 proxy
USER proxy
ENTRYPOINT ["socat", "TCP-LISTEN:18443,bind=127.0.0.1,fork,reuseaddr", "TCP:caddy:18443"]
