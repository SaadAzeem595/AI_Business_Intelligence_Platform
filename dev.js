const { spawn } = require("child_process");
const path = require("path");

const isWin = process.platform === "win32";

console.log("==> Launching DataPilot AI Business Intelligence Platform...");

// 1. Start Next.js Frontend
console.log("==> Starting Next.js Dev Server on port 3000...");
const nextDev = spawn(isWin ? "npx.cmd" : "npx", ["next", "dev"], {
  stdio: "inherit",
  shell: true
});

// 2. Start FastAPI Backend
console.log("==> Starting FastAPI Backend Server on port 8000...");
const pythonPath = isWin
  ? path.join(__dirname, "backend", ".venv", "Scripts", "python.exe")
  : path.join(__dirname, "backend", ".venv", "bin", "python");
const runScript = path.join(__dirname, "backend", "run.py");

const backendDev = spawn(pythonPath, [runScript], {
  stdio: "inherit",
  cwd: path.join(__dirname, "backend"),
  shell: true
});

// Handle processes shutdown gracefully on CTRL+C
const cleanup = () => {
  console.log("\n==> Shutting down development services...");
  try {
    nextDev.kill("SIGINT");
  } catch (e) {}
  try {
    backendDev.kill("SIGINT");
  } catch (e) {}
  process.exit();
};

process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);
process.on("exit", cleanup);
