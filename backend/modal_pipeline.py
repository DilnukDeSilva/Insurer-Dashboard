"""
Modal GPU pipeline for Gaussian Splatting.

Deploy once with:
    python3 -m modal deploy backend/modal_pipeline.py

The FastAPI backend calls run_pipeline.spawn(...) to start a job on a
cloud GPU. Step progress is written to R2 as jobs/{job_id}/status.json
so the backend can poll it and forward live updates to the frontend.
"""

import glob
import json
import subprocess
import time
from pathlib import Path

import modal

app = modal.App("insurer-pipeline")

# ---------------------------------------------------------------------------
# Container image — built once by Modal, cached forever after.
# First deploy takes ~20-30 min (compiling gsplat CUDA kernels).
# Subsequent runs start in ~10-20 seconds.
# ---------------------------------------------------------------------------
nerfstudio_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.0-devel-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install(
        "colmap",
        "git",
        "wget",
        "ffmpeg",
        "libgl1-mesa-glx",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender-dev",
        "libgomp1",
        "build-essential",
        "clang",   # required by pyliblzfse and fpsample (nerfstudio deps)
        "cargo",   # Rust compiler — required by fpsample
        "rustc",
    )
    .run_commands(
        "pip install --upgrade pip setuptools wheel",
        # PyTorch with CUDA 12.1
        "pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cu121",
        # nerfstudio compiles gsplat CUDA kernels at install time (nvcc from base image)
        "CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH pip install nerfstudio",
        "pip install boto3",
    )
)


@app.function(
    gpu="L4",        # 24 GB VRAM — ~$0.80/hr, ~10-15 min/job ≈ $0.15 per job
    image=nerfstudio_image,
    timeout=7200,    # 2-hour hard cap
)
def run_pipeline(
    job_id: str,
    r2_endpoint: str,
    r2_key_id: str,
    r2_secret: str,
    r2_bucket: str,
    images_prefix: str,
) -> dict:
    """
    Full 3DGS pipeline on a cloud GPU:
      1. Download images from R2
      2. COLMAP + transforms.json  (ns-process-data, GPU feature extraction)
      3. ns-train splatfacto       (CUDA — ~10-15 min on L4 for 3000 iters)
      4. ns-export gaussian-splat
      5. Upload splat.ply to R2 at  jobs/{job_id}/splat.ply
    """
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_key_id,
        aws_secret_access_key=r2_secret,
        config=Config(signature_version="s3v4"),
    )

    def put_status(steps: list, overall: str, error: str = "") -> None:
        body = json.dumps({"steps": steps, "overall": overall, "error": error})
        s3.put_object(
            Bucket=r2_bucket,
            Key=f"jobs/{job_id}/status.json",
            Body=body.encode(),
            ContentType="application/json",
        )

    def now() -> float:
        return time.time()

    # Force Qt headless for all subprocesses (COLMAP uses Qt internally)
    import os as _os
    _os.environ["QT_QPA_PLATFORM"] = "offscreen"
    _os.environ.pop("DISPLAY", None)

    def run(cmd: list, label: str = "") -> None:
        # No explicit env= so all children inherit our modified os.environ
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            name = label or cmd[0]
            raise RuntimeError(
                f"{name} failed (exit {result.returncode}):\n"
                f"STDOUT: {result.stdout[-3000:]}\n"
                f"STDERR: {result.stderr[-3000:]}"
            )

    steps = [
        {"key": "download", "status": "running",  "started_at": now()},
        {"key": "enhance",  "status": "pending"},
        {"key": "colmap",   "status": "pending"},
        {"key": "train",    "status": "pending"},
        {"key": "export",   "status": "pending"},
    ]
    put_status(steps, "running")

    try:
        # ── 1. Download images from R2 ──────────────────────────────────────
        images_dir = Path("/tmp/pipeline/images")
        images_dir.mkdir(parents=True, exist_ok=True)

        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=r2_bucket, Prefix=images_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                name = Path(key).name
                if name:
                    s3.download_file(r2_bucket, key, str(images_dir / name))

        steps[0].update({"status": "done", "completed_at": now()})
        steps[1].update({"status": "running", "started_at": now()})
        put_status(steps, "running")

        # ── 2. Enhance image brightness if dark ────────────────────────────
        #
        # Brightness tiers (mean pixel value out of 255):
        #
        #   < LOW_LIGHT (50) → SKIP 3D entirely.
        #                       Run Zero-DCE, upload enhanced photos to R2,
        #                       return "low_light" status. Frontend shows
        #                       the enhanced photos instead of a 3D model.
        #                       COLMAP cannot find enough features in photos
        #                       this dark even after enhancement.
        #
        #   < VERY_DARK (60) → Run Zero-DCE, then continue to COLMAP/train.
        #                       Photos are dark but may still have enough
        #                       texture for reconstruction after enhancement.
        #
        #   < DARK (100)     → Gamma correction only, then continue to 3D.
        #                       Photos are moderately dark (dim garage, dusk).
        #
        #   ≥ 100            → No enhancement, continue to 3D normally.
        #
        import math as _math
        import urllib.request as _urlreq
        import numpy as _np
        from PIL import Image, ImageStat

        LOW_LIGHT = 50.0   # mean < 50  → too dark for 3D, enhanced photos only
        VERY_DARK = 60.0   # mean < 60  → Zero-DCE then attempt 3D
        DARK      = 100.0  # mean < 100 → gamma correction then attempt 3D
        TARGET    = 140.0  # target mean brightness after enhancement

        image_files = sorted([
            f for f in images_dir.iterdir()
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ])

        if image_files:
            sample = image_files[:: max(1, len(image_files) // 6)][:6]
            means = [ImageStat.Stat(Image.open(p).convert("L")).mean[0] for p in sample]
            overall_mean = sum(means) / len(means)
            print(f"[pipeline] Mean image brightness: {overall_mean:.1f}/255")

            def _gamma_lut(mean: float, target: float) -> bytes:
                g = _math.log(target / 255.0) / _math.log(max(mean, 1.0) / 255.0)
                g = max(0.4, min(g, 2.5))
                return bytes([min(255, int((i / 255.0) ** (1.0 / g) * 255)) for i in range(256)])

            def _apply_gamma(files, lut: bytes) -> None:
                for p in files:
                    img = Image.open(p).convert("RGB")
                    img = img.point(lut * 3)
                    kw = {"quality": 95} if p.suffix.lower() in (".jpg", ".jpeg") else {}
                    img.save(p, **kw)

            def _run_zero_dce(files) -> bool:
                """Returns True on success, False on failure."""
                try:
                    import torch
                    import torch.nn as _nn

                    class _ZeroDCENet(_nn.Module):
                        def __init__(self):
                            super().__init__()
                            n = 32
                            self.relu = _nn.ReLU(inplace=True)
                            self.e_conv1 = _nn.Conv2d(3,   n,   3, 1, 1, bias=True)
                            self.e_conv2 = _nn.Conv2d(n,   n,   3, 1, 1, bias=True)
                            self.e_conv3 = _nn.Conv2d(n,   n,   3, 1, 1, bias=True)
                            self.e_conv4 = _nn.Conv2d(n,   n,   3, 1, 1, bias=True)
                            self.e_conv5 = _nn.Conv2d(n*2, n,   3, 1, 1, bias=True)
                            self.e_conv6 = _nn.Conv2d(n*2, n,   3, 1, 1, bias=True)
                            self.e_conv7 = _nn.Conv2d(n*2, 24,  3, 1, 1, bias=True)

                        def forward(self, x):
                            x1 = self.relu(self.e_conv1(x))
                            x2 = self.relu(self.e_conv2(x1))
                            x3 = self.relu(self.e_conv3(x2))
                            x4 = self.relu(self.e_conv4(x3))
                            x5 = self.relu(self.e_conv5(torch.cat([x3, x4], 1)))
                            x6 = self.relu(self.e_conv6(torch.cat([x2, x5], 1)))
                            xr = torch.tanh(self.e_conv7(torch.cat([x1, x6], 1)))
                            for r in torch.split(xr, 3, dim=1):
                                x = x + r * (x.pow(2) - x)
                            return x

                    weights_path = Path("/tmp/zerodce_weights.pth")
                    if not weights_path.exists():
                        print("[pipeline] Downloading Zero-DCE weights (~8 MB)…")
                        _urlreq.urlretrieve(
                            "https://github.com/Li-Chongyi/Zero-DCE/raw/master"
                            "/Zero-DCE_code/snapshots/Epoch99.pth",
                            str(weights_path),
                        )

                    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                    net = _ZeroDCENet().to(device)
                    net.load_state_dict(
                        torch.load(str(weights_path), map_location=device, weights_only=False)
                    )
                    net.eval()

                    MAX_DIM = 1920
                    with torch.no_grad():
                        for p in files:
                            img = Image.open(p).convert("RGB")
                            W, H = img.size
                            scale = min(1.0, MAX_DIM / max(W, H))
                            proc = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS) if scale < 1.0 else img

                            arr = _np.array(proc, dtype=_np.float32) / 255.0
                            t   = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
                            out = net(t).clamp(0.0, 1.0)
                            out_arr = (out.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255).astype(_np.uint8)
                            enhanced = Image.fromarray(out_arr)

                            if scale < 1.0:
                                enhanced = enhanced.resize((W, H), Image.LANCZOS)

                            kw = {"quality": 95} if p.suffix.lower() in (".jpg", ".jpeg") else {}
                            enhanced.save(p, **kw)

                            del t, out, out_arr
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()

                    print(f"[pipeline] Zero-DCE complete ({len(files)} images)")
                    return True
                except Exception as _e:
                    print(f"[pipeline] Zero-DCE failed ({_e})")
                    return False

            if overall_mean < LOW_LIGHT:
                # ── Too dark for 3D — enhance photos and exit early ────────
                #
                # Two-stage enhancement targeting shadow regions specifically:
                #   1. Zero-DCE      — neural net lifts shadows, restores structure
                #   2. Shadow lift   — aggressively boosts dark pixels (0–100/255)
                #                      while leaving bright pixels (180+/255) untouched.
                #                      This lifts the car body / tire area without
                #                      blowing out the background lights.
                #
                print(f"[pipeline] Critically dark (mean={overall_mean:.1f}) — low-light mode")

                # Build shadow-lift LUT:
                #   pixels 0–40%  brightness → gamma 2.0 boost (was 2.5 — reduced to limit noise)
                #   pixels 40–70% brightness → gradually blend back to no change
                #   pixels 70%+   brightness → no change (highlights preserved)
                def _shadow_lift_lut() -> bytes:
                    result = []
                    for i in range(256):
                        x = i / 255.0
                        if x < 0.4:
                            out = x ** (1.0 / 2.0)
                        elif x < 0.7:
                            t = (x - 0.4) / 0.3
                            shadow_out = x ** (1.0 / 2.0)
                            out = shadow_out * (1.0 - t) + x * t
                        else:
                            out = x
                        result.append(min(255, int(out * 255)))
                    return bytes(result)

                from PIL import ImageFilter as _IF

                # Stage 1: Zero-DCE (neural structure recovery)
                _run_zero_dce(image_files)

                # Stage 2: shadow lift — boosts dark areas, leaves highlights alone
                shadow_lut = _shadow_lift_lut()
                for p in image_files:
                    img = Image.open(p).convert("RGB")
                    img = img.point(shadow_lut * 3)
                    img.save(p, **{"quality": 95} if p.suffix.lower() in (".jpg", ".jpeg") else {})

                # Stage 3: noise reduction in YCbCr space
                #
                # Shadow lifting amplifies two types of sensor noise:
                #   • Color noise  (purple/green grain) → lives in Cb/Cr channels
                #                    → fix: Gaussian blur radius=3 on Cb and Cr
                #   • Luminance noise (gray grain/speckle) → lives in Y channel
                #                    → fix: MedianFilter(size=3) on Y
                #                       Median is better than Gaussian here because it
                #                       removes speckle while keeping edges sharp (car
                #                       outline, door handles, damage edges stay crisp).
                for p in image_files:
                    img = Image.open(p).convert("YCbCr")
                    y, cb, cr = img.split()
                    y  = y.filter(_IF.MedianFilter(size=3))       # luminance: remove grain, keep edges
                    cb = cb.filter(_IF.GaussianBlur(radius=3))    # color: remove purple/green cast
                    cr = cr.filter(_IF.GaussianBlur(radius=3))
                    img_out = Image.merge("YCbCr", (y, cb, cr)).convert("RGB")
                    img_out.save(p, **{"quality": 95} if p.suffix.lower() in (".jpg", ".jpeg") else {})

                print(f"[pipeline] Enhancement complete ({len(image_files)} images)")

                # Upload enhanced photos to R2 so frontend can display them
                for p in image_files:
                    s3.upload_file(
                        str(p), r2_bucket,
                        f"jobs/{job_id}/enhanced/{p.name}",
                    )
                print(f"[pipeline] Uploaded {len(image_files)} enhanced photos to R2")

                steps[1].update({"status": "done", "completed_at": now()})
                for step in steps[2:]:
                    step.update({"status": "skipped"})
                put_status(steps, "low_light")
                return {"low_light": True}

            elif overall_mean < VERY_DARK:
                # ── Zero-DCE then continue 3D pipeline ────────────────────
                print("[pipeline] Very dark — running Zero-DCE then continuing to 3D")
                if not _run_zero_dce(image_files):
                    _apply_gamma(image_files, _gamma_lut(overall_mean, TARGET))

            elif overall_mean < DARK:
                # ── PIL gamma correction for moderately dark images ─────────
                gamma_val = _math.log(TARGET / 255.0) / _math.log(max(overall_mean, 1.0) / 255.0)
                print(f"[pipeline] Moderately dark — gamma correction γ={gamma_val:.2f}")
                _apply_gamma(image_files, _gamma_lut(overall_mean, TARGET))

            else:
                print("[pipeline] Images well-lit — skipping enhancement")

        steps[1].update({"status": "done", "completed_at": now()})
        steps[2].update({"status": "running", "started_at": now()})
        put_status(steps, "running")

        # ── 3. COLMAP + transforms.json ─────────────────────────────────────
        processed_dir = Path("/tmp/pipeline/processed")
        colmap_db     = processed_dir / "colmap" / "database.db"
        colmap_sparse = processed_dir / "colmap" / "sparse"
        colmap_db.parent.mkdir(parents=True, exist_ok=True)
        colmap_sparse.mkdir(parents=True, exist_ok=True)

        # 2a. Feature extraction — CPU SIFT (GPU SIFT needs OpenGL which is
        #     unavailable in Modal's headless containers)
        run(["colmap", "feature_extractor",
             "--database_path", str(colmap_db),
             "--image_path",    str(images_dir),
             "--ImageReader.single_camera",  "1",
             "--ImageReader.camera_model",   "OPENCV",
             "--SiftExtraction.use_gpu",     "0",
             ], label="colmap feature_extractor")

        # 2b. Exhaustive matching — CPU mode (same headless OpenGL constraint)
        run(["colmap", "exhaustive_matcher",
             "--database_path",          str(colmap_db),
             "--SiftMatching.use_gpu",   "0",
             ], label="colmap exhaustive_matcher")

        # 2c. Sparse reconstruction (SfM)
        run(["colmap", "mapper",
             "--database_path", str(colmap_db),
             "--image_path",    str(images_dir),
             "--output_path",   str(colmap_sparse),
             ], label="colmap mapper")

        if not (colmap_sparse / "0").exists():
            raise RuntimeError(
                "COLMAP mapper produced no reconstruction. "
                "Not enough overlapping images to register cameras."
            )

        # 2d. Copy images and generate transforms.json from our COLMAP output
        import shutil as _shutil
        processed_images = processed_dir / "images"
        if not processed_images.exists():
            _shutil.copytree(str(images_dir), str(processed_images))

        run([
            "ns-process-data", "images",
            "--data",               str(images_dir),
            "--output-dir",         str(processed_dir),
            "--num-downscales",     "0",
            "--skip-colmap",
            "--colmap-model-path",  "colmap/sparse/0",
        ], label="ns-process-data (transforms.json)")

        steps[2].update({"status": "done", "completed_at": now()})
        steps[3].update({"status": "running", "started_at": now()})
        put_status(steps, "running")

        # ── 4. Train splatfacto (CUDA) ──────────────────────────────────────
        train_dir = Path("/tmp/pipeline/train")
        train_dir.mkdir(parents=True, exist_ok=True)

        run(
            [
                "ns-train", "splatfacto",
                "--data", str(processed_dir),
                "--output-dir", str(train_dir),
                "--experiment-name", "splat",
                "--max-num-iterations", "3000",
                "--steps-per-eval-image", "500",
                "--steps-per-eval-all-images", "3000",
                "--steps-per-save", "1000",
                "--machine.device-type", "cuda",
                "--vis", "tensorboard",
                "--viewer.quit-on-train-completion", "True",
                "nerfstudio-data",
            ],
            label="ns-train splatfacto (CUDA)",
        )

        steps[3].update({"status": "done", "completed_at": now()})
        steps[4].update({"status": "running", "started_at": now()})
        put_status(steps, "running")

        # ── 5. Export splat.ply ─────────────────────────────────────────────
        config_files = sorted(
            glob.glob(str(train_dir / "splat" / "splatfacto" / "*" / "config.yml"))
        )
        if not config_files:
            raise FileNotFoundError(f"ns-train produced no config.yml in {train_dir}")

        export_dir = Path("/tmp/pipeline/export")
        export_dir.mkdir(parents=True, exist_ok=True)

        # PyTorch 2.6 changed torch.load default to weights_only=True which blocks
        # several numpy types in nerfstudio checkpoints. Patch torch.load to
        # restore the pre-2.6 default (weights_only=False) rather than
        # whack-a-moling individual numpy types one by one.
        export_wrapper = Path("/tmp/pipeline/run_export.py")
        export_wrapper.write_text(
            "import sys, torch\n"
            "_orig_load = torch.load\n"
            "def _patched_load(*args, **kwargs):\n"
            "    kwargs.setdefault('weights_only', False)\n"
            "    return _orig_load(*args, **kwargs)\n"
            "torch.load = _patched_load\n"
            "from nerfstudio.scripts.exporter import entrypoint\n"
            "sys.exit(entrypoint())\n"
        )

        run(
            [
                "python3", str(export_wrapper), "gaussian-splat",
                "--load-config", config_files[-1],
                "--output-dir", str(export_dir),
            ],
            label="ns-export gaussian-splat",
        )

        ply_files = list(export_dir.glob("*.ply"))
        if not ply_files:
            raise FileNotFoundError(f"ns-export produced no .ply in {export_dir}")

        # ── 5. Upload splat.ply to R2 ───────────────────────────────────────
        splat_r2_key = f"jobs/{job_id}/splat.ply"
        s3.upload_file(str(ply_files[0]), r2_bucket, splat_r2_key)

        steps[4].update({"status": "done", "completed_at": now()})
        put_status(steps, "completed")

        return {"splat_key": splat_r2_key}

    except Exception as exc:
        for step in steps:
            if step["status"] == "running":
                step.update({"status": "failed", "completed_at": now()})
        put_status(steps, "failed", error=str(exc))
        raise
