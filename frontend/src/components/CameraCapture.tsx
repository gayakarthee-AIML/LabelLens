import { useEffect, useRef, useState, useCallback } from "react";
import { analyzeFrame, type QualityReport } from "@/services/imageQuality";

interface CameraCaptureProps {
  onCapture: (dataUrl: string, quality: QualityReport) => void;
  guidanceLabel: string;
}

// Real browser camera access via getUserMedia — no simulated frames. Falls
// back to a file input (still a genuine capture from the device camera on
// mobile, via the `capture` attribute) if getUserMedia is unavailable or
// permission is denied, per the brief's requirement to handle camera failure
// gracefully rather than dead-end the inspector.
export function CameraCapture({ onCapture, guidanceLabel }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [torchOn, setTorchOn] = useState(false);
  const [torchSupported, setTorchSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ dataUrl: string; quality: QualityReport } | null>(null);
  const [live, setLive] = useState(false);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startStream = useCallback(async () => {
    setError(null);
    stopStream();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode, width: { ideal: 1920 }, height: { ideal: 1440 } },
        audio: false
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setLive(true);

      const [track] = stream.getVideoTracks();
      const capabilities = track.getCapabilities?.() as MediaTrackCapabilities & { torch?: boolean };
      setTorchSupported(!!capabilities?.torch);
    } catch (err) {
      setLive(false);
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Camera permission denied. Allow camera access, or use image upload below."
          : "Camera unavailable on this device. Use image upload below."
      );
    }
  }, [facingMode, stopStream]);

  useEffect(() => {
    void startStream();
    return () => stopStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode]);

  const toggleTorch = async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    try {
      await track.applyConstraints({ advanced: [{ torch: !torchOn } as any] });
      setTorchOn(!torchOn);
    } catch {
      /* torch control not supported by this device/browser */
    }
  };

  const capture = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const quality = analyzeFrame(canvas);
    setPreview({ dataUrl: canvas.toDataURL("image/jpeg", 0.9), quality });
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d")!;
        ctx.drawImage(img, 0, 0);
        const quality = analyzeFrame(canvas);
        setPreview({ dataUrl: canvas.toDataURL("image/jpeg", 0.9), quality });
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  };

  const retake = () => setPreview(null);

  const confirm = () => {
    if (!preview) return;
    onCapture(preview.dataUrl, preview.quality);
    setPreview(null);
  };

  return (
    <div>
      <div className="camera-frame">
        {preview ? (
          <img src={preview.dataUrl} alt="Captured frame" />
        ) : live ? (
          <video ref={videoRef} playsInline muted />
        ) : (
          <div style={{ color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", height: "100%", padding: 16, textAlign: "center", fontSize: 13.5 }}>
            {error ?? "Starting camera…"}
          </div>
        )}
        {!preview && <div className="camera-guidance">{guidanceLabel}</div>}
      </div>

      {preview && preview.quality.flags.length > 0 && (
        <div className="quality-flags">
          {preview.quality.flags.map((f) => (
            <span className="quality-flag" key={f}>
              {f.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
      {preview && <p style={{ fontSize: 12.5, color: "var(--color-steel)", marginTop: 6 }}>{preview.quality.feedback.join(" ")}</p>}

      <div className="camera-actions">
        {preview ? (
          <>
            <button className="btn secondary" onClick={retake} type="button">Retake</button>
            <button className="btn" onClick={confirm} type="button">Confirm</button>
          </>
        ) : (
          <>
            <button className="btn" onClick={capture} type="button" disabled={!live}>Capture</button>
            <button
              className="btn secondary"
              type="button"
              onClick={() => setFacingMode((m) => (m === "environment" ? "user" : "environment"))}
            >
              Switch camera
            </button>
            {torchSupported && (
              <button className="btn secondary" type="button" onClick={toggleTorch}>
                {torchOn ? "Torch off" : "Torch on"}
              </button>
            )}
            <button className="btn secondary" type="button" onClick={() => fileInputRef.current?.click()}>
              Upload image
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: "none" }}
              onChange={handleFileUpload}
            />
          </>
        )}
      </div>
    </div>
  );
}
