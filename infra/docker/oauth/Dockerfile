FROM python:3.12-alpine

WORKDIR /app
COPY token_server.py /app/token_server.py

ENV LAB_OAUTH_CLIENT_ID=lab-client
ENV LAB_OAUTH_CLIENT_SECRET=lab-secret
ENV LAB_OAUTH_ACCESS_TOKEN=lab-access-token
ENV LAB_OAUTH_EXPIRES_IN=3600

EXPOSE 9090

CMD ["python", "/app/token_server.py"]
