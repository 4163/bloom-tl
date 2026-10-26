// Portable raster PSD I/O. This module does not draw text or repair backgrounds.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { initializeCanvas, readPsd, writePsdBuffer } from 'ag-psd';
import { PNG } from 'pngjs';

const MAX_PIXELS = 32_000_000;
initializeCanvas(
  () => { throw new Error('Canvas rendering is disabled. Use raster imageData.'); },
  (width, height) => ({ width, height, data: new Uint8ClampedArray(width * height * 4) }),
);
const require = (condition, message) => { if (!condition) throw new Error(message); };
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function dimensions(width, height) {
  require(Number.isInteger(width) && width > 0 && Number.isInteger(height) && height > 0
    && width * height <= MAX_PIXELS, 'Invalid canvas or canvas exceeds 32 million pixels.');
}
function raster(filename) {
  const bytes = fs.readFileSync(filename);
  require(bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'Layer rasters must be lossless PNG files.');
  dimensions(bytes.readUInt32BE(16), bytes.readUInt32BE(20));
  const image = PNG.sync.read(bytes, { checkCRC: true });
  dimensions(image.width, image.height);
  return { width: image.width, height: image.height, data: image.data };
}
function savePng(filename, image) {
  fs.writeFileSync(filename, PNG.sync.write({ width: image.width, height: image.height, data: Buffer.from(image.data) }));
}
function readRasterPsd(filename, layers = false) {
  const bytes = fs.readFileSync(filename);
  require(bytes.length >= 26 && bytes.toString('ascii', 0, 4) === '8BPS' && bytes.readUInt16BE(4) === 1, 'Use a PSD file, not PSB.');
  dimensions(bytes.readUInt32BE(18), bytes.readUInt32BE(14));
  require(bytes.readUInt16BE(22) === 8 && bytes.readUInt16BE(24) === 3, 'Save the PSD as 8-bit RGB with a merged compatibility image.');
  const psd = readPsd(bytes, { useImageData: true, skipThumbnail: true, skipLinkedFilesData: true,
    skipLayerImageData: !layers });
  require(psd.imageData?.data?.length === psd.width * psd.height * 4, 'The PSD has no merged preview. Save it with compatibility data enabled.');
  return psd;
}

function storedLayerNames(bytes) {
  // Read the flat PSD record sequence directly, independently of ag-psd's tree.
  let offset = 26;
  for (let section = 0; section < 2; section++) offset += 4 + bytes.readUInt32BE(offset);
  require(bytes.readUInt32BE(offset) > 0 && bytes.readUInt32BE(offset + 4) > 0, 'PSD layer records are missing.');
  offset += 8;
  const count = Math.abs(bytes.readInt16BE(offset));
  offset += 2;
  const names = [];
  for (let index = 0; index < count; index++) {
    const channels = bytes.readUInt16BE(offset + 16);
    offset += 18 + channels * 6 + 12;
    const extraLength = bytes.readUInt32BE(offset);
    const end = offset + 4 + extraLength;
    offset += 4;
    offset += 4 + bytes.readUInt32BE(offset); // Layer mask data.
    offset += 4 + bytes.readUInt32BE(offset); // Blending ranges.
    names.push(bytes.toString('ascii', offset + 1, offset + 1 + bytes[offset]));
    require(end <= bytes.length, 'Invalid PSD layer record length.');
    offset = end;
  }
  return names;
}

function writeVerifiedPsd(psd, output, topFirstNames) {
  const bytes = writePsdBuffer(psd, { generateThumbnail: false, trimImageData: false });
  require(JSON.stringify(storedLayerNames(bytes)) === JSON.stringify([...topFirstNames].reverse()),
    'PSD records must store original, paint and text from background to foreground.');
  fs.writeFileSync(output, bytes);
  const roundTrip = readRasterPsd(output, true);
  require(digest(roundTrip.imageData.data) === digest(psd.imageData.data), 'PSD composite round-trip mismatch.');
  require(roundTrip.children.length === psd.children.length, 'PSD layer count mismatch.');
  psd.children.forEach((layer, index) => {
    const actual = roundTrip.children[index];
    require(actual.name === layer.name, 'PSD layer name changed.');
    if (layer.imageData) require(digest(actual.imageData.data) === digest(layer.imageData.data), `PSD raster layer changed: ${layer.name}`);
  });
  return { file: output, layers: topFirstNames, layer_order_verified: true, sha256: digest(bytes) };
}

export function exportPsd(manifestFile, output) {
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
  dimensions(manifest.width, manifest.height);
  require(Array.isArray(manifest.layers) && manifest.layers.length === 3, 'Provide English text, cleanup paint and original raster layers, top first.');
  const resolve = filename => path.resolve(path.dirname(manifestFile), filename);
  const composite = raster(resolve(manifest.composite));
  require(composite.width === manifest.width && composite.height === manifest.height, 'Composite dimensions differ from the document.');
  const children = manifest.layers.map(layer => {
    const imageData = raster(resolve(layer.file));
    const left = layer.left ?? 0, top = layer.top ?? 0;
    require(left === 0 && top === 0 && imageData.width === manifest.width && imageData.height === manifest.height,
      'Each layer must use the complete page canvas at the origin.');
    return { name: layer.name, left, top, imageData, opacity: 1, blendMode: 'normal',
      protected: layer.locked ? { transparency: true, position: true, composite: true, all: true } : undefined };
  });
  require(children[0].imageData.data.some((value, index) => index % 4 === 3 && value === 0), 'The text raster must have a transparent background.');
  const paint = children[1].imageData.data, original = children[2].imageData.data;
  for (let index = 0; index < paint.length; index += 4) {
    require(!(paint[index + 3] && original[index + 3] === 255
      && paint[index] === original[index] && paint[index + 1] === original[index + 1] && paint[index + 2] === original[index + 2]),
    'Cleanup paint must be transparent outside the native cleanup.');
  }
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'manga-psd-'));
  const composed = path.join(temporary, 'composed.png');
  try {
    execFileSync(process.env.FFMPEG || 'ffmpeg', ['-hide_banner', '-loglevel', 'error',
      '-i', resolve(manifest.layers[2].file), '-i', resolve(manifest.layers[1].file), '-i', resolve(manifest.layers[0].file),
      '-filter_complex', '[0:v][1:v]overlay=0:0:format=auto:alpha=straight[clean];[clean][2:v]overlay=0:0:format=auto:alpha=straight,format=rgb24',
      '-frames:v', '1', composed], { timeout: 120000, windowsHide: true, stdio: 'pipe', maxBuffer: 1024 * 1024 });
    require(digest(raster(composed).data) === digest(composite.data), 'Original, paint and text layers do not reproduce the rendered page.');
  } finally {
    if (fs.existsSync(composed)) fs.unlinkSync(composed);
    fs.rmdirSync(temporary);
  }
  // ag-psd writes children in PSD record order, from background to foreground.
  // Keep the public layer manifest top first and reverse only at serialization.
  const psd = { width: manifest.width, height: manifest.height, imageData: composite, children: [...children].reverse() };
  return writeVerifiedPsd(psd, output, children.map(layer => layer.name));
}

export function previewPsd(input, output, expectedWidth, expectedHeight) {
  const psd = readRasterPsd(input);
  require(psd.width === expectedWidth && psd.height === expectedHeight, 'PSD dimensions do not match the selected page.');
  savePng(output, psd.imageData);
  return { file: output, width: psd.width, height: psd.height, sha256: digest(fs.readFileSync(output)) };
}

export function validatePng(input, output, expectedWidth, expectedHeight) {
  const image = PNG.sync.read(fs.readFileSync(input), { checkCRC: true });
  require(image.width === expectedWidth && image.height === expectedHeight, 'PNG dimensions do not match the selected page.');
  fs.copyFileSync(input, output);
  return { file: output, width: image.width, height: image.height, sha256: digest(fs.readFileSync(output)) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const [command, input, output, width, height] = process.argv.slice(2);
    require(input && output, 'Use export manifest.json output.psd, or preview input.psd output.png width height.');
    require(!fs.existsSync(output), 'Output already exists. Use a new filename.');
    const result = command === 'export' ? exportPsd(path.resolve(input), path.resolve(output))
      : command === 'preview' ? previewPsd(input, output, Number(width), Number(height))
        : command === 'validate-png' ? validatePng(input, output, Number(width), Number(height)) : null;
    require(result, 'Unknown PSD command.');
    console.log(JSON.stringify(result));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
