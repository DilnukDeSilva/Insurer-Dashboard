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

        # ── 2. COLMAP + transforms.json ─────────────────────────────────────
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

        steps[1].update({"status": "done", "completed_at": now()})
        steps[2].update({"status": "running", "started_at": now()})
        put_status(steps, "running")

        # ── 3. Train splatfacto (CUDA) ──────────────────────────────────────
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

        steps[2].update({"status": "done", "completed_at": now()})
        steps[3].update({"status": "running", "started_at": now()})
        put_status(steps, "running")

        # ── 4. Export splat.ply ─────────────────────────────────────────────
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

        steps[3].update({"status": "done", "completed_at": now()})
        put_status(steps, "completed")

        return {"splat_key": splat_r2_key}

    except Exception as exc:
        for step in steps:
            if step["status"] == "running":
                step.update({"status": "failed", "completed_at": now()})
        put_status(steps, "failed", error=str(exc))
        raise
