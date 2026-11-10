FROM python:3.13-alpine AS builder
WORKDIR /site
COPY build.py ./
COPY assets ./assets
COPY content ./content
COPY pwa ./pwa
RUN python build.py

FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /site/dist/ /usr/share/nginx/html/
EXPOSE 8080
