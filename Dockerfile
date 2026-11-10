FROM python:3.13-alpine AS builder
WORKDIR /site
COPY build.py ./
COPY legal.py ./
COPY auth-public.json ./
COPY assets ./assets
COPY content ./content
COPY pwa ./pwa
ARG SUPABASE_URL
ARG SUPABASE_PUBLISHABLE_KEY
ENV SUPABASE_URL=$SUPABASE_URL SUPABASE_PUBLISHABLE_KEY=$SUPABASE_PUBLISHABLE_KEY
RUN python build.py

FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /site/dist/ /usr/share/nginx/html/
EXPOSE 8080
