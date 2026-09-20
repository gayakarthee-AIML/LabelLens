// Client-side pre-capture quality checks. These run instantly in the browser
// on the captured frame so an inspector gets feedback ("too dark", "hold
// steady") before the image is ever uploaded — the authoritative blur/glare/
// perspective analysis still happens server-side in
// backend/app/services/cv_service.py against the full-resolution image.
export interface QualityReport {
  brightness: number; // 0..255
  blurScore: number; // higher = sharper (variance of Laplacian approximation)
  glarePct: number; // 0..1
  flags: string[];
  feedback: string[];
}

function toGrayscale(imageData: ImageData): Float32Array {
  const { data, width, height } = imageData;
  const gray = new Float32Array(width * height);
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    gray[p] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }
  return gray;
}

// Discrete Laplacian convolution used as a cheap sharpness proxy.
function laplacianVariance(gray: Float32Array, width: number, height: number): number {
  const kernel = [0, 1, 0, 1, -4, 1, 0, 1, 0];
  let sum = 0;
  let sumSq = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      let acc = 0;
      let k = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          acc += gray[(y + dy) * width + (x + dx)] * kernel[k++];
        }
      }
      sum += acc;
      sumSq += acc * acc;
      count++;
    }
  }
  const mean = sum / count;
  return sumSq / count - mean * mean;
}

export function analyzeFrame(canvas: HTMLCanvasElement): QualityReport {
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return { brightness: 0, blurScore: 0, glarePct: 0, flags: ["ANALYSIS_UNAVAILABLE"], feedback: [] };
  }

  // Downscale for speed — sharpness/brightness signal survives a 320px-wide sample.
  const scale = Math.min(1, 320 / canvas.width);
  const sw = Math.max(1, Math.round(canvas.width * scale));
  const sh = Math.max(1, Math.round(canvas.height * scale));
  const sampleCanvas = document.createElement("canvas");
  sampleCanvas.width = sw;
  sampleCanvas.height = sh;
  const sctx = sampleCanvas.getContext("2d")!;
  sctx.drawImage(canvas, 0, 0, sw, sh);
  const imageData = sctx.getImageData(0, 0, sw, sh);

  const gray = toGrayscale(imageData);
  const brightness = gray.reduce((a, b) => a + b, 0) / gray.length;
  const blurScore = laplacianVariance(gray, sw, sh);

  let brightPixels = 0;
  for (let i = 0; i < gray.length; i++) if (gray[i] > 245) brightPixels++;
  const glarePct = brightPixels / gray.length;

  const flags: string[] = [];
  const feedback: string[] = [];

  if (brightness < 60) {
    flags.push("LOW_BRIGHTNESS");
    feedback.push("Too dark — move to better lighting.");
  } else if (brightness > 220) {
    flags.push("OVEREXPOSED");
    feedback.push("Image is overexposed — reduce direct light.");
  }

  if (blurScore < 15) {
    flags.push("BLUR_DETECTED");
    feedback.push("Image appears blurry — hold the device steady.");
  }

  if (glarePct > 0.12) {
    flags.push("GLARE_DETECTED");
    feedback.push("Glare detected on the label — tilt the package slightly.");
  }

  if (flags.length === 0) {
    feedback.push("Label detected — image quality looks good.");
  }

  return { brightness, blurScore, glarePct, flags, feedback };
}
