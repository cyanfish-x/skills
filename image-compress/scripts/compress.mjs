#!/usr/bin/env node
/**
 * image-compress — thin wrapper around sharp.
 *
 * Usage:
 *   node scripts/compress.mjs <input> [output] [options]
 *
 * Options:
 *   --max-bytes <500KB|2MB|bytes>  target size cap; lowers quality until met
 *   --quality <1-100>              encoding quality (default 70)
 *   --format <jpeg|webp|png>       convert format; only when explicitly given
 *   --max-dimension <px>           resize so both sides <= px; only when explicitly given
 */
import { readFile, writeFile } from 'node:fs/promises'
import { basename, dirname, extname, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import sharp from 'sharp'

const DEFAULT_QUALITY = 70
const DEFAULT_MAX_ROUNDS = 3
const EXT_BY_MEDIA_TYPE = {
  'image/jpeg': '.jpg',
  'image/webp': '.webp',
  'image/png': '.png',
  'image/gif': '.gif',
}

function parseBytes(value) {
  if (typeof value === 'number') return value
  const m = String(value).trim().match(/^(\d+(?:\.\d+)?)\s*(b|kb|mb)?$/i)
  if (!m) throw new Error(`invalid size: ${value}`)
  const n = Number(m[1])
  const unit = (m[2] || 'b').toLowerCase()
  if (unit === 'kb') return Math.round(n * 1024)
  if (unit === 'mb') return Math.round(n * 1024 * 1024)
  return Math.round(n)
}

function clampQuality(n) {
  const q = Math.round(Number(n))
  if (!Number.isFinite(q) || q < 1 || q > 100) {
    throw new Error(`--quality must be an integer between 1 and 100, got ${n}`)
  }
  return q
}

function clampDimension(n) {
  const d = Math.round(Number(n))
  if (!Number.isFinite(d) || d < 1) throw new Error(`--max-dimension must be a positive integer, got ${n}`)
  return d
}

function parseArgs(argv) {
  const positional = []
  const options = {
    quality: DEFAULT_QUALITY,
  }

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--max-bytes') {
      options.maxBytes = argv[++i]
    } else if (a.startsWith('--max-bytes=')) {
      options.maxBytes = a.slice('--max-bytes='.length)
    } else if (a === '--quality') {
      options.quality = Number(argv[++i])
    } else if (a.startsWith('--quality=')) {
      options.quality = Number(a.slice('--quality='.length))
    } else if (a === '--format') {
      options.format = argv[++i]
    } else if (a.startsWith('--format=')) {
      options.format = a.slice('--format='.length)
    } else if (a === '--max-dimension') {
      options.maxDimension = Number(argv[++i])
    } else if (a.startsWith('--max-dimension=')) {
      options.maxDimension = Number(a.slice('--max-dimension='.length))
    } else if (a === '-h' || a === '--help') {
      console.log(`Usage: node scripts/compress.mjs <input> [output] [--max-bytes 500KB] [--quality 70] [--format webp] [--max-dimension 2000]`)
      process.exit(0)
    } else {
      positional.push(a)
    }
  }

  return { positional, options }
}

function mediaTypeFromMetaFormat(format) {
  switch (format) {
    case 'jpeg':
      return 'image/jpeg'
    case 'webp':
      return 'image/webp'
    case 'png':
      return 'image/png'
    case 'gif':
      return 'image/gif'
    default:
      return 'image/jpeg'
  }
}

function buildQualitySequence(startQuality) {
  const seq = []
  for (let q = startQuality; q > 1; q -= 10) seq.push(q)
  seq.push(1)
  return seq
}

async function encodeOnce(input, { quality, format, maxDimension }) {
  const pipeline = sharp(input, {
    animated: true,
    failOn: 'none',
    limitInputPixels: false,
  })
  const meta = await pipeline.metadata()
  const width = meta.width ?? 0
  const height = meta.height ?? 0

  if (maxDimension) {
    pipeline.resize({
      width: maxDimension,
      height: maxDimension,
      fit: 'inside',
      withoutEnlargement: true,
    })
  }

  const targetFormat = format ?? meta.format ?? 'jpeg'
  let output
  let mediaType

  switch (targetFormat) {
    case 'jpeg':
      output = pipeline.jpeg({ quality, mozjpeg: true })
      mediaType = 'image/jpeg'
      break
    case 'webp':
      output = pipeline.webp({ quality })
      mediaType = 'image/webp'
      break
    case 'png':
      output = pipeline.png({ quality, compressionLevel: 9 })
      mediaType = 'image/png'
      break
    case 'gif':
      output = pipeline.gif()
      mediaType = 'image/gif'
      break
    default:
      output = pipeline.jpeg({ quality, mozjpeg: true })
      mediaType = 'image/jpeg'
  }

  const buf = await output.toBuffer({ resolveWithObject: true })
  return {
    data: new Uint8Array(buf.data),
    bytes: buf.data.byteLength,
    width: buf.info.width,
    height: buf.info.height,
    mediaType,
  }
}

export async function compressImage(input, options = {}) {
  const maxBytes = options.maxBytes == null ? null : parseBytes(options.maxBytes)
  const initialQuality = clampQuality(options.quality ?? DEFAULT_QUALITY)
  const maxDimension = options.maxDimension == null ? null : clampDimension(options.maxDimension)
  const format = options.format ? String(options.format).toLowerCase() : null
  const maxRounds = options.maxRounds ?? DEFAULT_MAX_ROUNDS

  const original = Buffer.from(input)
  const originalBytes = original.byteLength

  if (maxBytes != null && originalBytes <= maxBytes) {
    const meta = await sharp(original, { failOn: 'none' }).metadata()
    return {
      data: new Uint8Array(original),
      bytes: originalBytes,
      width: meta.width ?? 0,
      height: meta.height ?? 0,
      mediaType: mediaTypeFromMetaFormat(meta.format),
      quality: null,
      originalBytes,
      achieved: true,
      rounds: 0,
    }
  }

  if (maxBytes == null) {
    const result = await encodeOnce(original, { quality: initialQuality, format, maxDimension })
    return {
      ...result,
      quality: initialQuality,
      originalBytes,
      achieved: true,
      rounds: 1,
    }
  }

  let current = original
  let best = {
    data: new Uint8Array(original),
    bytes: originalBytes,
    width: 0,
    height: 0,
    mediaType: null,
  }
  let rounds = 0

  for (let round = 1; round <= maxRounds; round++) {
    rounds = round
    for (const quality of buildQualitySequence(initialQuality)) {
      const candidate = await encodeOnce(current, { quality, format, maxDimension })
      if (candidate.bytes < best.bytes) {
        best = { ...candidate, quality }
      }
      if (candidate.bytes <= maxBytes) {
        return {
          ...candidate,
          quality,
          originalBytes,
          achieved: true,
          rounds,
        }
      }
    }
    if (round < maxRounds && best.bytes < originalBytes) {
      current = Buffer.from(best.data)
    }
  }

  return {
    ...best,
    quality: best.quality ?? null,
    originalBytes,
    achieved: false,
    rounds,
  }
}

async function main() {
  const { positional, options } = parseArgs(process.argv.slice(2))
  if (positional.length < 1) {
    console.error('Usage: node scripts/compress.mjs <input> [output] [options]')
    process.exit(1)
  }

  const inputPath = positional[0]
  const input = await readFile(inputPath)
  const result = await compressImage(input, options)

  const defaultExt = EXT_BY_MEDIA_TYPE[result.mediaType] ?? '.jpg'
  const outPath =
    positional[1] ??
    join(dirname(inputPath), `${basename(inputPath, extname(inputPath))}.compressed${defaultExt}`)

  await writeFile(outPath, result.data)
  console.log(
    JSON.stringify(
      {
        input: inputPath,
        output: outPath,
        originalBytes: result.originalBytes,
        bytes: result.bytes,
        achieved: result.achieved,
        quality: result.quality,
        width: result.width,
        height: result.height,
        mediaType: result.mediaType,
        rounds: result.rounds,
      },
      null,
      2,
    ),
  )
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href
if (isMain) {
  main().catch((err) => {
    console.error(err)
    process.exit(1)
  })
}