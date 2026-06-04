FROM node:18-bullseye-slim

WORKDIR /app

# Copy package manifests first to leverage Docker layer caching
COPY package.json package-lock.json* /app/

# Avoid optional deps and use legacy peer deps to reduce install failures
ENV NPM_CONFIG_OPTIONAL=false
RUN if [ -f package-lock.json ]; then \
			npm ci --no-audit --no-fund --legacy-peer-deps; \
		else \
			npm install --no-audit --no-fund --legacy-peer-deps; \
		fi

# Copy application source
COPY . /app

EXPOSE 3000

CMD ["npm", "run", "dev"]
