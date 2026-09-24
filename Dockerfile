FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN rm -f .env*
# Inject public build-time env vars
ARG NEXT_PUBLIC_API_URL=https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io/api/v1
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_YWNjZXB0ZWQtcmFtLTYyLmNsZXJrLmFjY291bnRzLmRldiQ
ARG NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_51Tx076BGNo9NDajkvYhtvPfvAcW2FKqbFZgSr1CXBCX7w7pJO16c0P3aRapYIIwFa4YHLUe2VXFhzcuT2fdcD0m10095xRxMgS
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=$NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_DEV_AUTH_BYPASS=false
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
