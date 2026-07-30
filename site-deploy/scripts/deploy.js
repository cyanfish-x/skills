#!/usr/bin/env node
/**
 * deploy.js — rclone 增量同步本地构建产物，可选腾讯云 CDN 刷新。
 *
 * 用法:
 *   node deploy.js [--cwd <projectRoot>] [--env <envFile>] [--skip-cdn]
 */

import {
  parseArgs,
  resolveEnvPath,
  loadEnv,
  loadDeployConfig,
  assertSyncConfig,
  ensureRemoteDir,
  syncFilesByRclone,
  refreshCdn,
} from "./common.js"

function printHelp() {
  console.log(`Usage: node deploy.js [--cwd <projectRoot>] [--env <envFile>] [--skip-cdn]

  --cwd       Project root (default: process.cwd()). Env defaults to <cwd>/actions/.env
  --env       Explicit path to .env
  --skip-cdn  Sync only; do not call Tencent CDN purge
`)
}

async function main() {
  const options = parseArgs()
  if (options.help) {
    printHelp()
    return
  }

  try {
    const envPath = resolveEnvPath(options)
    loadEnv(envPath)
    const config = loadDeployConfig()
    assertSyncConfig(config, { cwd: options.cwd })

    await ensureRemoteDir(config)
    await syncFilesByRclone(config)

    if (options.skipCdn) {
      console.log("ℹ️ 已指定 --skip-cdn，跳过 CDN 刷新")
    } else {
      await refreshCdn(config, { strict: false })
    }

    console.log("🎉 部署全流程结束！")
  } catch (error) {
    console.error("❌ 部署过程中止:", error.message || error)
    process.exitCode = 1
  }
}

main()
