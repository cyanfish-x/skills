#!/usr/bin/env node
/**
 * refresh-cdn.js — 仅刷新腾讯云 CDN 路径缓存。
 *
 * 用法:
 *   node refresh-cdn.js [--cwd <projectRoot>] [--env <envFile>]
 */

import {
  parseArgs,
  resolveEnvPath,
  loadEnv,
  loadDeployConfig,
  refreshCdn,
} from "./common.js"

function printHelp() {
  console.log(`Usage: node refresh-cdn.js [--cwd <projectRoot>] [--env <envFile>]

  --cwd  Project root (default: process.cwd()). Env defaults to <cwd>/actions/.env
  --env  Explicit path to .env

Fails with non-zero exit if CDN config is missing or the API call fails.
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
    await refreshCdn(config, { strict: true })
  } catch (error) {
    console.error("❌ CDN 刷新失败:", error.message || error)
    process.exitCode = 1
  }
}

main()
