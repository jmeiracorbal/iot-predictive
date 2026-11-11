FROM nodered/node-red:5.0.9

COPY --chown=node-red:node-red flows.json /data/flows.json
COPY --chown=node-red:node-red healthcheck.js /data/healthcheck.js

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=12 CMD node /data/healthcheck.js
