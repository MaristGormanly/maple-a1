FROM node:24-slim AS build

WORKDIR /app/client

COPY client/package.json client/package-lock.json ./
RUN npm ci

COPY client ./
RUN npm run build -- --configuration docker

FROM nginx:1.27-alpine

COPY client/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/client/dist/maple-client/browser /usr/share/nginx/html

EXPOSE 80
