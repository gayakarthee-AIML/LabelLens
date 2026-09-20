import { useEffect, useRef, useState, useCallback } from "react";
import { analyzeFrame } from "@/services/imageQuality";
import type { CapturedImage, ImageSlot } from "@/types";

// Video spin-capture: the inspector slowly rotates the product in front of
// the camera instead of taking individual static shots. A live video feed
// is sampled every ~500ms onto an offscreen canvas; each candidate frame is
// scored with the SAME client-side quality heuristic CameraCapture already
// uses (services/imageQuality.ts — blur/brightness/glare), and compared
// against the last KEPT frame with a cheap perceptual diff so near-duplicate
// frames (camera held still) are discarded automatically. Kept frames
// upload as ordinary images to numbered slots (spin_frame_1, spin_frame_2,
// …) — InspectionImage.slot is a free string on the backend, so this needs
// no schema change — and flow through the exact same preprocess -> OCR ->
// declaration-extraction pipeline as any other captured photo.
const SAMPLE_INTERVAL_MS = 500;
const MAX_FRAMES = 10;
const MIN_BLUR_SCORE = 15;
const DIFF_THUMB_SIZE = 20;
const MIN_DIFF_TO_KEEP = 12; // mean abs diff (0-255 scale) between kept-frame thumbnails

interface KeptFrame {
  dataUrl: string;
  qualityFlags: string[];
}

function grayThumbnail(video: HTMLVideoElement, canvas: HTMLCanvasElement): Uint8ClampedArray {
  canvas.width = DIFF_THUMB_SIZE;
  canvas.height = DIFF_THUMB_SIZE;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(video, 0, 0, DIFF_THUMB_SIZE, DIFF_THUMB_SIZE);
  const { data } = ctx.getImageData(0, 0, DIFF_THUMB_SIZE, DIFF_THUMB_SIZE);
  const gray = new Uint8ClampedArray(DIFF_THUMB_SIZE * DIFF_THUMB_SIZE);
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    gray[p] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }
  return gray;
}

function meanAbsDiff(a: Uint8ClampedArray, b: Uint8ClampedArray): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += Math.abs(a[i] - b[i]);
  return sum / a.length;
}

export function SpinCapture({
  slotPrefix,
  onComplete,
  onCancel
}: {
  slotPrefix: string;
  onComplete: (images: CapturedImage[]) => void;
  onCancel: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const sampleCanvasRef = useRef<HTMLCanvasElement>(document.createElement("canvas"));
  const diffCanvasRef = useRef<HTMLCanvasElement>(document.createElement("canvas"));
  const streamRef = useRef<MediaStream | null>(null);
  const lastKeptThumbRef = useRef<Uint8ClampedArray | null>(null);
  const intervalRef = useRef<number | null>(null);

  const [live, setLive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [frames, setFrames] = useState<KeptFrame[]>([]);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startStream = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setLive(true);
    } catch {
      setLive(false);
      setError("Camera unavailable — spin-scan needs live camera access. Use individual photo capture instead.");
    }
  }, []);

  useEffect(() => {
    void startStream();
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
      stopStream();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sampleFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return;

    const thumb = grayThumbnail(video, diffCanvasRef.current);
    if (lastKeptThumbRef.current && meanAbsDiff(thumb, lastKeptThumbRef.current) < MIN_DIFF_TO_KEEP) {
      return; // too similar to the last kept frame — camera likely held still
    }

    const canvas = sampleCanvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(video, 0, 0);
    const quality = analyzeFrame(canvas);
    if (quality.blurScore < MIN_BLUR_SCORE) return; // too blurry — likely mid-rotation motion blur

    lastKeptThumbRef.current = thumb;
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setFrames((prev) => (prev.length >= MAX_FRAMES ? prev : [...prev, { dataUrl, qualityFlags: quality.flags }]));
  }, []);

  const startRecording = () => {
    setFrames([]);
    lastKeptThumbRef.current = null;
    setRecording(true);
    intervalRef.current = window.setInterval(sampleFrame, SAMPLE_INTERVAL_MS);
  };

  const stopRecording = () => {
    setRecording(false);
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const finish = () => {
    stopRecording();
    const images: CapturedImage[] = frames.map((f, i) => ({
      slot: `${slotPrefix}_${i + 1}` as ImageSlot,
      dataUrl: f.dataUrl,
      capturedAt: new Date().toISOString(),
      qualityFlags: f.qualityFlags,
      uploaded: false
    }));
    onComplete(images);
  };

  return (
    <div>
      <div className="camera-frame">
        {error ? (
          <p style={{ color: "var(--color-violation-red)", padding: 16 }}>{error}</p>
        ) : (
          <video ref={videoRef} playsInline muted style={{ width: "100%" }} />
        )}
      </div>
      <p style={{ fontSize: 12.5, color: "var(--color-steel)", marginTop: 8 }}>
        Slowly rotate the product in front of the camera, keeping it centered and in focus. Sharp,
        distinct angles are kept automatically — held-still or blurry frames are skipped.
      </p>

      {frames.length > 0 && (
        <div className="spin-thumb-strip">
          {frames.map((f, i) => (
            <img key={i} src={f.dataUrl} alt={`spin frame ${i + 1}`} />
          ))}
        </div>
      )}

      <div className="camera-actions">
        {!recording ? (
          <button className="btn" type="button" disabled={!live} onClick={startRecording}>
            {frames.length > 0 ? "Restart Spin Scan" : "Start Spin Scan"}
          </button>
        ) : (
          <button className="btn" type="button" onClick={stopRecording}>
            Stop ({frames.length} frame{frames.length === 1 ? "" : "s"} captured)
          </button>
        )}
        <button className="btn secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
        {!recording && frames.length > 0 && (
          <button className="btn" type="button" onClick={finish}>
            Use These {frames.length} Frame{frames.length === 1 ? "" : "s"}
          </button>
        )}
      </div>
    </div>
  );
}
