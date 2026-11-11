const http = require("node:http");

const port = Number(process.env.PORT);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
    process.exit(1);
}

const request = http.get(
    { hostname: "127.0.0.1", port, path: "/health", timeout: 3000 },
    response => {
        response.resume();
        process.exit(response.statusCode === 200 ? 0 : 1);
    }
);

request.on("error", () => process.exit(1));
request.on("timeout", () => request.destroy());
