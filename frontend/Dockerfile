FROM node:22-alpine AS build

ARG VITE_AGENT_NAME=Noname助手
ENV VITE_AGENT_NAME=${VITE_AGENT_NAME}

WORKDIR /app
COPY frontend/package.json /app/package.json
RUN npm install
COPY frontend /app
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
