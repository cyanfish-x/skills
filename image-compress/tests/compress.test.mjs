import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { compressImage } from '../scripts/compress.mjs'

// Resolve sharp from scripts/node_modules so tests don't depend on a root install.
const require = createRequire(new URL('../scripts/package.json', import.meta.url))
const sharp = require('sharp')

async function solidPng(width, height) {
  return sharp({
    create: {
      width,
      height,
      channels: 3,
      background: { r: 20, g: 120, b: 200 },
    },
  })
    .png()
    .toBuffer()
}

async function noiseJpeg(width, height, quality = 95) {
  const size = width * height * 3
  const data = Buffer.alloc(size)
  for (let i = 0; i < size; i++) {
    data[i] = Math.floor(Math.random() * 256)
  }
  return sharp(data, { raw: { width, height, channels: 3 } })
    .jpeg({ quality })
    .toBuffer()
}

test('default compression keeps format and dimensions, uses quality 70', async () => {
  const input = await solidPng(800, 600)
  const out = await compressImage(input)

  assert.equal(out.quality, 70)
  assert.equal(out.width, 800)
  assert.equal(out.height, 600)
  assert.equal(out.mediaType, 'image/png')
  assert.equal(out.data[0], 0x89)
  assert.equal(out.data[1], 0x50)
})

test('format is only converted when format option is provided', async () => {
  const input = await solidPng(800, 600)

  const same = await compressImage(input)
  assert.equal(same.mediaType, 'image/png')
  assert.equal(same.data[0], 0x89)

  const webp = await compressImage(input, { format: 'webp' })
  const webpBuf = Buffer.from(webp.data)
  assert.equal(webp.mediaType, 'image/webp')
  assert.equal(webpBuf.toString('latin1', 0, 4), 'RIFF')
  assert.equal(webpBuf.toString('latin1', 8, 12), 'WEBP')
})

test('dimensions are only resized when maxDimension is provided', async () => {
  const input = await solidPng(4000, 3000)

  const unchanged = await compressImage(input)
  assert.equal(unchanged.width, 4000)
  assert.equal(unchanged.height, 3000)

  const fitted = await compressImage(input, { maxDimension: 2000 })
  assert.ok(fitted.width <= 2000)
  assert.ok(fitted.height <= 2000)
  assert.equal(fitted.width / fitted.height, 4 / 3)
})

test('maxBytes lowers quality until target is achieved', async () => {
  const input = await noiseJpeg(1200, 900, 95)
  const target = 300 * 1024
  assert.ok(input.byteLength > target, 'fixture should start above target')

  const out = await compressImage(input, { maxBytes: target })
  assert.equal(out.achieved, true)
  assert.ok(out.bytes <= target)
  assert.ok(out.quality <= 70)
})

test('impossible maxBytes returns best effort after max 3 rounds', async () => {
  const input = await noiseJpeg(1200, 900, 95)
  const out = await compressImage(input, { maxBytes: 100 })

  assert.equal(out.achieved, false)
  assert.ok(out.rounds <= 3)
  assert.ok(out.bytes < input.byteLength)
})

test('input already under maxBytes is passed through unchanged', async () => {
  const input = await solidPng(100, 100)
  const out = await compressImage(input, { maxBytes: 10 * 1024 * 1024 })

  assert.equal(out.achieved, true)
  assert.equal(out.bytes, input.byteLength)
})