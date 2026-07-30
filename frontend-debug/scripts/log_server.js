#!/usr/bin/env node
/**
 * frontend-debug 本地日志收集服务（Node 零依赖，仅用 http/fs/path）
 *
 * 职责：
 *   1. 监听端口，接收浏览器埋点 fetch 上报的日志
 *   2. 处理 CORS 预检（OPTIONS）+ 跨域头，解决浏览器跨域拦截
 *   3. 把每条日志追加写入工作区下 .frontend-debug/logs.jsonl（每行一条 JSON）
 *
 * 生命周期由 agent 用后台 Bash 管理：
 *   启动：node log_server.js [--port 7559] [--reset]   （agent 用 run_in_background 启动）
 *   停止：kill 进程（agent 记录启动时返回的 PID）
 *
 * 输出约定：
 *   stdout 打印服务地址、日志文件绝对路径、PID（供 agent 读取后告知用户 / 停服）
 *   请求处理失败不中断服务，仅 stderr 打印
 *
 * 日志文件是唯一状态载体：agent 用 Read/grep 读取验证，不依赖进程内状态。
 */

const http = require("http");
const fs = require("fs");
const path = require("path");

// ---------- 参数解析 ----------
const argv = process.argv.slice(2);
function getArg(name, def) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : def;
}
const PORT = Number(getArg("--port", 7559));
const RESET = argv.includes("--reset");

// ---------- 路径 ----------
// 日志目录 = 当前工作目录下的 .frontend-debug（agent 应在目标项目根目录启动本服务）
const LOG_DIR = path.resolve(process.cwd(), ".frontend-debug");
const LOG_FILE = path.join(LOG_DIR, "logs.jsonl");

// ---------- CORS 头 ----------
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Debug-Session-Id"
};

// ---------- 日志写入 ----------
function appendLog(record) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(LOG_FILE, JSON.stringify(record) + "\n", "utf8");
  } catch (e) {
    process.stderr.write("[log_server] 写日志失败: " + e.message + "\n");
  }
}

if (RESET) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.writeFileSync(LOG_FILE, "", "utf8");
    process.stderr.write("[log_server] 已清空旧日志: " + LOG_FILE + "\n");
  } catch (e) {
    process.stderr.write("[log_server] 清空日志失败: " + e.message + "\n");
  }
}

// ---------- HTTP 服务 ----------
function createServer(port) {
  const server = http.createServer((req, res) => {
    // 统一注入 CORS 头
    for (const [k, v] of Object.entries(CORS_HEADERS)) {
      res.setHeader(k, v);
    }

    // 预检请求：直接 204 放行
    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    // 只接受 POST /ingest*
    if (req.method !== "POST" || !req.url.startsWith("/ingest")) {
      res.writeHead(404);
      res.end("not found");
      return;
    }

    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      // 防御超大请求体（单条 >2MB 直接丢弃）
      if (body.length > 2 * 1024 * 1024) {
        body = "";
        req.destroy();
      }
    });
    req.on("end", () => {
      if (!body) {
        res.writeHead(400);
        res.end("empty body");
        return;
      }
      try {
        const parsed = JSON.parse(body);
        // URL 路径尾段可作为 probe_id（兼容 /ingest/H1 写法），body 内优先
        const urlTail = req.url.split("/").pop();
        const record = {
          ts: parsed.timestamp || Date.now(),
          probe_id: parsed.probe_id || urlTail || "unknown",
          location: parsed.location || "",
          message: parsed.message || "",
          data: parsed.data || null,
          session_id: parsed.sessionId || req.headers["x-debug-session-id"] || ""
        };
        appendLog(record);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        process.stderr.write("[log_server] 解析失败: " + e.message + "\n");
        res.writeHead(400);
        res.end("bad json");
      }
    });
  });

  return server;
}

// ---------- 启动（端口冲突自动 +1 重试，最多 10 次） ----------
function startAt(port) {
  const server = createServer(port);
  server.on("error", (err) => {
    if (err.code === "EADDRINUSE" && port < PORT + 10) {
      process.stderr.write("[log_server] 端口 " + port + " 被占用，尝试 " + (port + 1) + "\n");
      startAt(port + 1);
    } else {
      process.stderr.write("[log_server] 启动失败: " + err.message + "\n");
      process.exit(1);
    }
  });
  server.listen(port, "127.0.0.1", () => {
    const actualPort = server.address().port;
    // 关键输出：供 agent 读取
    process.stdout.write(
      JSON.stringify({
        ok: true,
        url: "http://127.0.0.1:" + actualPort,
        port: actualPort,
        logFile: LOG_FILE,
        pid: process.pid
      }) + "\n"
    );
    process.stderr.write(
      "[log_server] 监听 http://127.0.0.1:" + actualPort + " → " + LOG_FILE + "\n"
    );
  });
}

startAt(PORT);
