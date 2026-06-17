FROM node:22-slim AS deps

WORKDIR /app
COPY apps/web/package.json /app/package.json
RUN npm install

FROM node:22-slim AS build

WORKDIR /app
COPY --from=deps /app/node_modules /app/node_modules
COPY apps/web /app
RUN npm run build

FROM node:22-slim

WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone /app
COPY --from=build /app/.next/static /app/.next/static
COPY --from=build /app/public /app/public

EXPOSE 3000

CMD ["node", "server.js"]
