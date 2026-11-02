FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS builder
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -S -g 10001 nodeapp && adduser -S -u 10001 -G nodeapp nodeapp
COPY --from=builder --chown=nodeapp:nodeapp /app/.next/standalone ./
COPY --from=builder --chown=nodeapp:nodeapp /app/.next/static ./.next/static
USER nodeapp
EXPOSE 3000
CMD ["node", "server.js"]
