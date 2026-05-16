"""Zero-Reference Deep Curve Estimation for low-light image enhancement."""

from pathlib import Path

from app.config import settings


class ZeroDCEService:
    """Runs Zero-DCE enhancement before photogrammetry when lighting is poor."""

    def __init__(self) -> None:
        self.repo_dir = settings.zero_dce_repo_dir
        self.weights = settings.zero_dce_weights

    @property
    def is_configured(self) -> bool:
        return bool(
            self.repo_dir
            and self.repo_dir.is_dir()
            and self.weights
            and self.weights.is_file()
        )

    def enhance_images(self, input_dir: Path, output_dir: Path) -> Path:
        """
        Enhance all images in `input_dir` and write results to `output_dir`.

        Wire this to your Zero-DCE inference script (PyTorch) once weights are in place.
        Expected layout: input_dir/*.jpg|png -> output_dir/enhanced_*
        """
        if not self.is_configured:
            raise RuntimeError(
                "Zero-DCE is not configured. Set ZERO_DCE_REPO_DIR and ZERO_DCE_WEIGHTS in .env"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        # TODO: invoke Zero-DCE model, e.g.:
        # subprocess.run(
        #     ["python", str(self.repo_dir / "test.py"), ...],
        #     check=True,
        # )

        raise NotImplementedError(
            "Zero-DCE inference is not implemented yet. Add your model call in enhance_images()."
        )
