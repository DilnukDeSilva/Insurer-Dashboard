"""Gaussian Splatting pipeline using COLMAP (via ns-process-data) + nerfstudio splatfacto."""

import glob
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

# Homebrew and common user-install paths where nerfstudio CLI tools land
_EXTRA_PATHS = [
    "/opt/homebrew/bin",
    "/opt/homebrew/opt/python@3.11/bin",
    "/opt/homebrew/opt/python@3.12/bin",
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / "Library" / "Python" / "3.11" / "bin"),
    str(Path.home() / "Library" / "Python" / "3.12" / "bin"),
]

def _env_with_brew() -> dict:
    """Return an environment dict that includes Homebrew paths."""
    env = os.environ.copy()
    existing = env.get("PATH", "")
    extra = ":".join(p for p in _EXTRA_PATHS if p not in existing)
    env["PATH"] = f"{extra}:{existing}" if extra else existing
    return env

def _find_tool(name: str) -> str:
    """Return full path to a CLI tool, searching extra paths. Raises if not found."""
    env = _env_with_brew()
    for directory in env["PATH"].split(":"):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise FileNotFoundError(
        f"'{name}' not found in PATH.\n"
        f"Install with:\n"
        f"  brew install python@3.11 colmap\n"
        f"  /opt/homebrew/opt/python@3.11/bin/pip3.11 install torch torchvision\n"
        f"  /opt/homebrew/opt/python@3.11/bin/pip3.11 install nerfstudio"
    )


class GaussianSplattingService:
    """Runs COLMAP SfM + nerfstudio splatfacto to produce a Gaussian Splat PLY."""

    @property
    def is_configured(self) -> bool:
        try:
            _find_tool("ns-process-data")
            _find_tool("ns-train")
            _find_tool("ns-export")
            _find_tool("colmap")
            return True
        except FileNotFoundError:
            return False

    def _run(self, cmd: list[str], cwd: Optional[Path] = None, label: str = "") -> None:
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                env=_env_with_brew(),
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Tool not found: {cmd[0]}\n"
                f"Install nerfstudio and colmap first — see backend logs for instructions."
            ) from e
        except subprocess.CalledProcessError as e:
            name = label or cmd[0].split("/")[-1]
            raise RuntimeError(
                f"{name} failed (exit {e.returncode}):\n"
                f"STDOUT: {e.stdout[-3000:] if e.stdout else '(empty)'}\n"
                f"STDERR: {e.stderr[-3000:] if e.stderr else '(empty)'}"
            ) from e

    def run(
        self,
        images_dir: Path,
        output_dir: Path,
        on_step: Optional[Callable[[str, object], None]] = None,
    ) -> Path:
        """
        Full Gaussian Splatting pipeline.
        Returns path to the exported splats.ply file.
        """
        from app.schemas.pipeline import StepStatus

        if not self.is_configured:
            raise RuntimeError(
                "Gaussian Splatting tools not installed.\n"
                "Run in terminal:\n"
                "  brew install python@3.11 colmap\n"
                "  /opt/homebrew/opt/python@3.11/bin/pip3.11 install torch torchvision\n"
                "  /opt/homebrew/opt/python@3.11/bin/pip3.11 install nerfstudio"
            )

        def mark(key: str, s: object) -> None:
            if on_step:
                on_step(key, s)

        output_dir.mkdir(parents=True, exist_ok=True)
        processed_dir = output_dir / "processed"
        train_dir = output_dir / "train"

        ns_process = _find_tool("ns-process-data")
        ns_train = _find_tool("ns-train")
        ns_export = _find_tool("ns-export")
        colmap_bin = _find_tool("colmap")

        # Step 1: Run COLMAP directly (nerfstudio uses old --SiftExtraction.use_gpu
        # flag that was renamed to --FeatureExtraction.use_gpu in COLMAP 4.x)
        mark("colmap", StepStatus.RUNNING)

        colmap_db = processed_dir / "colmap" / "database.db"
        colmap_sparse = processed_dir / "colmap" / "sparse"
        colmap_db.parent.mkdir(parents=True, exist_ok=True)
        colmap_sparse.mkdir(parents=True, exist_ok=True)

        # 1a. Feature extraction
        self._run([
            colmap_bin, "feature_extractor",
            "--database_path", str(colmap_db),
            "--image_path", str(images_dir),
            "--ImageReader.single_camera", "1",
            "--ImageReader.camera_model", "OPENCV",
        ], label="colmap feature_extractor")

        # 1b. Exhaustive matching
        self._run([
            colmap_bin, "exhaustive_matcher",
            "--database_path", str(colmap_db),
        ], label="colmap exhaustive_matcher")

        # 1c. Sparse reconstruction (SfM)
        self._run([
            colmap_bin, "mapper",
            "--database_path", str(colmap_db),
            "--image_path", str(images_dir),
            "--output_path", str(colmap_sparse),
        ], label="colmap mapper")

        # Check mapper produced output
        sparse_model = colmap_sparse / "0"
        if not sparse_model.exists():
            raise RuntimeError(
                "COLMAP mapper produced no reconstruction. "
                "Not enough overlapping images to register cameras — "
                "ensure photos have good overlap (walk around the car)."
            )

        # 1d. Let ns-process-data create transforms.json from our COLMAP output
        # Copy images to processed dir first (ns-process-data expects them there)
        processed_images = processed_dir / "images"
        if not processed_images.exists():
            import shutil as _shutil
            _shutil.copytree(str(images_dir), str(processed_images))

        self._run([
            ns_process, "images",
            "--data", str(images_dir),
            "--output-dir", str(processed_dir),
            "--num-downscales", "0",
            "--skip-colmap",  # use our COLMAP output above
            "--colmap-model-path", "colmap/sparse/0",  # relative to output-dir
        ], label="ns-process-data (transforms)")

        mark("colmap", StepStatus.DONE)

        # Step 2: Train splatfacto on Apple Silicon (MPS device)
        mark("train", StepStatus.RUNNING)
        self._run(
            [
                ns_train, "splatfacto",
                "--data", str(processed_dir),
                "--output-dir", str(train_dir),
                "--experiment-name", "splat",
                "--max-num-iterations", "3000",
                "--steps-per-eval-image", "500",   # default 100 is expensive on MPS
                "--steps-per-eval-all-images", "3000",
                "--steps-per-save", "1000",
                "--machine.device-type", "mps",  # Apple Silicon Metal GPU
                "--vis", "tensorboard",           # headless — no browser viewer
                "--viewer.quit-on-train-completion", "True",
                "nerfstudio-data",
            ],
            label="ns-train splatfacto",
        )
        mark("train", StepStatus.DONE)

        # Step 3: Export splats.ply
        mark("export", StepStatus.RUNNING)

        config_files = glob.glob(str(train_dir / "splat" / "splatfacto" / "*" / "config.yml"))
        if not config_files:
            raise FileNotFoundError(f"ns-train produced no config.yml in {train_dir}")
        config_path = sorted(config_files)[-1]

        export_dir = output_dir / "splat"
        export_dir.mkdir(parents=True, exist_ok=True)

        self._run(
            [
                ns_export, "gaussian-splat",
                "--load-config", config_path,
                "--output-dir", str(export_dir),
            ],
            label="ns-export",
        )

        ply_candidates = list(export_dir.glob("*.ply"))
        if not ply_candidates:
            raise FileNotFoundError(f"ns-export produced no .ply in {export_dir}")

        splat_ply = export_dir / "splat.ply"
        if not splat_ply.exists():
            shutil.move(str(ply_candidates[0]), str(splat_ply))

        mark("export", StepStatus.DONE)
        return splat_ply
