/**
 * Shared helpers for site-deploy scripts.
 */

import fs from "node:fs"
import path from "node:path"
import { spawn, spawnSync } from "node:child_process"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)

export function parseArgs(argv = process.argv.slice(2)) {
  const options = {
    cwd: process.cwd(),
    envFile: null,
    skipCdn: false,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === "--cwd" && argv[i + 1]) {
      options.cwd = path.resolve(argv[++i])
      continue
    }
    if (arg === "--env" && argv[i + 1]) {
      options.envFile = path.resolve(argv[++i])
      continue
    }
    if (arg === "--skip-cdn") {
      options.skipCdn = true
      continue
    }
    if (arg === "--help" || arg === "-h") {
      options.help = true
    }
  }

  return options
}

export function resolveEnvPath(options) {
  if (options.envFile) {
    return options.envFile
  }
  return path.resolve(options.cwd, "actions", ".env")
}

export function loadEnv(envPath) {
  const dotenv = require("dotenv")
  if (!fs.existsSync(envPath)) {
    throw new Error(`环境文件不存在: ${envPath}`)
  }
  dotenv.config({ path: envPath })
}

export function parseCdnFlushPaths(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function loadDeployConfig() {
  return {
    localDir: process.env.LOCAL_DIR,
    remoteDir: process.env.REMOTE_DIR,
    rclone: {
      remote: process.env.RCLONE_REMOTE,
      transfers: process.env.RCLONE_TRANSFERS || "8",
      checkers: process.env.RCLONE_CHECKERS || "16",
    },
    cdn: {
      secretId: process.env.CDN_SECRET_ID,
      secretKey: process.env.CDN_SECRET_KEY,
      flushPaths: parseCdnFlushPaths(process.env.CDN_FLUSH_PATHS),
      region: process.env.CDN_REGION || "ap-chengdu",
    },
  }
}

export function normalizeRcloneRemoteName(remote) {
  return String(remote).trim().replace(/:$/, "")
}

export function createRemoteTarget(config) {
  return `${normalizeRcloneRemoteName(config.rclone.remote)}:${config.remoteDir}`
}

export function assertCommandAvailable(command, message) {
  const result = spawnSync(command, ["version"], {
    stdio: "ignore",
    shell: false,
  })

  if (result.error || result.status !== 0) {
    throw new Error(message)
  }
}

export function assertRcloneRemoteExists(remote) {
  const remoteName = normalizeRcloneRemoteName(remote)
  const result = spawnSync("rclone", ["listremotes"], {
    encoding: "utf8",
    shell: false,
  })

  if (result.error || result.status !== 0) {
    throw new Error("无法读取 rclone remote 列表，请先确认 rclone config 可用")
  }

  const remotes = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/:$/, ""))
    .filter(Boolean)

  if (!remotes.includes(remoteName)) {
    throw new Error(`rclone remote 不存在: ${remoteName}，请先执行 rclone config 创建它`)
  }
}

export function assertSyncConfig(config, { cwd }) {
  const requiredFields = [
    ["LOCAL_DIR", config.localDir],
    ["REMOTE_DIR", config.remoteDir],
    ["RCLONE_REMOTE", config.rclone.remote],
  ]

  const missingFields = requiredFields
    .filter(([, value]) => !value)
    .map(([name]) => name)

  if (missingFields.length > 0) {
    throw new Error(`缺少必要环境变量: ${missingFields.join(", ")}`)
  }

  const localDir = path.isAbsolute(config.localDir)
    ? config.localDir
    : path.resolve(cwd, config.localDir)

  if (!fs.existsSync(localDir)) {
    throw new Error(`本地同步目录不存在: ${localDir}`)
  }

  config.localDir = localDir

  assertCommandAvailable(
    "rclone",
    "未找到 rclone，请先安装 rclone 并确认它已加入 PATH（可由 site-deploy skill 征询后代装）"
  )
  assertRcloneRemoteExists(config.rclone.remote)
}

export function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      shell: false,
      ...options,
    })

    child.on("error", reject)
    child.on("close", (code) => {
      if (code === 0) {
        resolve()
        return
      }
      reject(new Error(`${command} 执行失败，退出码: ${code}`))
    })
  })
}

export async function ensureRemoteDir(config) {
  console.log(`🔌 正在确认远程目录 ${config.remoteDir}...`)
  await runCommand("rclone", ["mkdir", createRemoteTarget(config)])
  console.log("✅ 远程目录已就绪")
}

export async function syncFilesByRclone(config) {
  const localSource = path.resolve(config.localDir)
  const remoteTarget = createRemoteTarget(config)

  console.log(`🚀 正在增量同步 ${localSource} -> ${remoteTarget}`)
  await runCommand("rclone", [
    "sync",
    localSource,
    remoteTarget,
    "--exclude=.user.ini",
    "--progress",
    "--transfers",
    config.rclone.transfers,
    "--checkers",
    config.rclone.checkers,
    "--fast-list",
  ])
  console.log("✅ rclone 增量同步完成")
}

/**
 * @param {object} config
 * @param {{ strict?: boolean }} [opts] strict=true 时失败抛错（refresh-cdn）；false 时只打日志（deploy）
 */
export async function refreshCdn(config, opts = {}) {
  const strict = opts.strict === true

  if (!config.cdn.secretId || !config.cdn.secretKey) {
    const message = "未配置 CDN_SECRET_ID 或 CDN_SECRET_KEY，跳过 CDN 刷新"
    if (strict) {
      throw new Error(message)
    }
    console.warn(`⚠️ ${message}`)
    return
  }

  if (config.cdn.flushPaths.length === 0) {
    const message = "未配置 CDN_FLUSH_PATHS，跳过 CDN 刷新"
    if (strict) {
      throw new Error(message)
    }
    console.warn(`⚠️ ${message}`)
    return
  }

  console.log("🔄 正在刷新 CDN 缓存...")

  const tencentcloud = require("tencentcloud-sdk-nodejs-cdn")
  const CdnClient = tencentcloud.cdn.v20180606.Client

  const client = new CdnClient({
    credential: {
      secretId: config.cdn.secretId,
      secretKey: config.cdn.secretKey,
    },
    region: config.cdn.region,
    profile: {
      httpProfile: {
        endpoint: "cdn.tencentcloudapi.com",
      },
    },
  })

  const params = {
    Paths: config.cdn.flushPaths,
    FlushType: "flush",
  }

  try {
    const data = await client.PurgePathCache(params)
    console.log("✅ CDN 刷新请求提交成功:", data)
  } catch (err) {
    if (strict) {
      throw err
    }
    console.error("❌ CDN 刷新失败", err)
  }
}

export function scriptsDir() {
  return __dirname
}
