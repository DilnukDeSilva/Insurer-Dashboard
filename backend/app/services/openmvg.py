"""OpenMVG structure-from-motion and sparse reconstruction."""

import struct
import subprocess
from pathlib import Path
from typing import Callable, Optional

from app.config import settings


def _jpeg_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) from a JPEG file by reading SOF marker."""
    with open(path, "rb") as f:
        data = f.read()
    i = 0
    while i < len(data) - 8:
        if data[i] == 0xFF:
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h = struct.unpack(">H", data[i + 5 : i + 7])[0]
                w = struct.unpack(">H", data[i + 7 : i + 9])[0]
                return w, h
            elif marker in (0xD8, 0xD9, 0x01) or (0xD0 <= marker <= 0xD7):
                i += 2
                continue
            else:
                length = struct.unpack(">H", data[i + 2 : i + 4])[0]
                i += 2 + length
        else:
            i += 1
    return 0, 0


def _estimate_focal_pixels(images_dir: Path) -> Optional[int]:
    """Estimate focal length in pixels from first JPEG (1.2 × max dimension)."""
    for img in sorted(images_dir.glob("*.jpg"))[:1]:
        w, h = _jpeg_dimensions(img)
        if w and h:
            return int(max(w, h) * 1.2)
    return None


class OpenMVGService:
    """Wraps OpenMVG CLI tools for SfM pipeline stages."""

    SFM_TOOLS = (
        "openMVG_main_SfMInit_ImageListing",
        "openMVG_main_ComputeFeatures",
        "openMVG_main_ComputeMatches",
        "openMVG_main_GeometricFilter",
        "openMVG_main_SfM",
        "openMVG_main_openMVG2openMVS",
    )

    def __init__(self) -> None:
        self.bin_dir = settings.openmvg_bin_dir

    @property
    def is_configured(self) -> bool:
        if not self.bin_dir or not self.bin_dir.is_dir():
            return False
        return all((self.bin_dir / tool).exists() for tool in self.SFM_TOOLS)

    def _binary(self, name: str) -> Path:
        if not self.bin_dir:
            raise RuntimeError("OPENMVG_BIN_DIR is not set")
        path = self.bin_dir / name
        if not path.exists():
            raise FileNotFoundError(f"OpenMVG binary not found: {path}")
        return path

    def _sensor_db(self) -> Optional[Path]:
        """Find the OpenMVG sensor width database if available."""
        candidates = [
            Path.home() / "openMVG" / "src" / "openMVG" / "exif" / "sensor_width_database" / "sensor_width_camera_database.txt",
        ]
        if self.bin_dir:
            candidates.append(self.bin_dir.parent.parent.parent / "src" / "openMVG" / "exif" / "sensor_width_database" / "sensor_width_camera_database.txt")
        for path in candidates:
            if path.exists():
                return path
        return None

    def _run(self, cmd: list[str]) -> None:
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def run_sfm(
        self,
        images_dir: Path,
        output_dir: Path,
        on_step: Optional[Callable[[str, object], None]] = None,
    ) -> Path:
        """
        Run incremental OpenMVG SfM on images_dir.
        Returns path to the exported scene.mvs file for OpenMVS.
        """
        from app.schemas.pipeline import StepStatus

        def mark(key: str, s: object) -> None:
            if on_step:
                on_step(key, s)

        if not self.is_configured:
            raise RuntimeError(
                "OpenMVG is not configured. Set OPENMVG_BIN_DIR to your install/bin path."
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        matches_dir = output_dir / "matches"
        reconstruction_dir = output_dir / "reconstruction"
        matches_dir.mkdir(parents=True, exist_ok=True)
        reconstruction_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Image listing
        # Always pass -f as a fallback focal length — images from R2 have no EXIF
        # camera model so the sensor DB cannot resolve intrinsics on its own.
        listing_cmd = [
            str(self._binary("openMVG_main_SfMInit_ImageListing")),
            "-i", str(images_dir),
            "-o", str(matches_dir),
        ]
        focal = _estimate_focal_pixels(images_dir)
        if focal:
            listing_cmd += ["-f", str(focal)]
        sensor_db = self._sensor_db()
        if sensor_db:
            listing_cmd += ["-d", str(sensor_db)]
        self._run(listing_cmd)

        # Step 2: Compute SIFT features — force upright=false and high peak threshold
        # to extract as many keypoints as possible from small/compressed images
        mark("features", StepStatus.RUNNING)
        self._run([
            str(self._binary("openMVG_main_ComputeFeatures")),
            "-i", str(matches_dir / "sfm_data.json"),
            "-o", str(matches_dir),
            "-m", "SIFT",
            "-u", "0",   # don't restrict to upright keypoints — use all orientations
            "-f", "1",   # force recompute (skip cache)
        ])
        mark("features", StepStatus.DONE)

        # Step 3a: Putative matching — use ANN for speed with ratio test
        mark("matching", StepStatus.RUNNING)
        self._run([
            str(self._binary("openMVG_main_ComputeMatches")),
            "-i", str(matches_dir / "sfm_data.json"),
            "-o", str(matches_dir / "matches.putative.bin"),
            "-r", "0.8",  # Lowe ratio threshold (0.8 = more matches, less strict)
        ])

        # Step 3b: Geometric filtering (fundamental matrix)
        self._run([
            str(self._binary("openMVG_main_GeometricFilter")),
            "-i", str(matches_dir / "sfm_data.json"),
            "-m", str(matches_dir / "matches.putative.bin"),
            "-o", str(matches_dir / "matches.f.bin"),
            "-g", "f",
        ])
        mark("matching", StepStatus.DONE)

        # Step 4: Incremental SfM
        mark("sfm", StepStatus.RUNNING)
        self._run([
            str(self._binary("openMVG_main_SfM")),
            "-i", str(matches_dir / "sfm_data.json"),
            "-m", str(matches_dir),
            "-o", str(reconstruction_dir),
            "-s", "INCREMENTAL",
        ])
        mark("sfm", StepStatus.DONE)

        # Step 5: Export to OpenMVS format
        # Must run from the backend working dir because sfm_data.bin stores
        # image paths relative to where the server process started.
        mark("export", StepStatus.RUNNING)
        mvs_file = output_dir / "scene.mvs"
        undistorted_dir = output_dir / "undistorted"
        undistorted_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                str(self._binary("openMVG_main_openMVG2openMVS")),
                "-i", str(reconstruction_dir / "sfm_data.bin"),
                "-o", str(mvs_file),
                "-d", str(undistorted_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(settings.data_dir.parent),
        )
        mark("export", StepStatus.DONE)

        return mvs_file

    def run_command(self, tool: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a single OpenMVG binary with arguments."""
        cmd = [str(self._binary(tool)), *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
