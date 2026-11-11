const http = require("node:http");

const request = http.get(
    { hostname: "127.0.0.1", port: 1880, path: "/health", timeout: 3000 },
    response => {
        response.resume();
        process.exit(response.statusCode === 200 ? 0 : 1);
    }
);

request.on("error", () => process.exit(1));
request.on("timeout", () => request.destroy());
