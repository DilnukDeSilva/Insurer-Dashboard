"""Zero-Reference Deep Curve Estimation for low-light image enhancement."""

import math
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageStat

from app.config import settings

WEIGHTS_URL = (
    "https://github.com/Li-Chongyi/Zero-DCE/raw/master"
    "/Zero-DCE_code/snapshots/Epoch99.pth"
)
_DEFAULT_WEIGHTS_CACHE = Path.home() / ".cache" / "insurer_dashboard" / "zerodce_Epoch99.pth"


class ZeroDCEService:
    """Runs Zero-DCE for low-light image enhancement. No external repo required —
    the network is defined inline and weights are auto-downloaded on first use."""

    VERY_DARK = 60.0   # mean < 60  → Zero-DCE (deep learning)
    DARK      = 100.0  # mean < 100 → PIL gamma correction
    TARGET    = 140.0  # target mean brightness after enhancement
    MAX_DIM   = 1920   # cap long edge before inference to limit memory

    def __init__(self, weights_path: Optional[Path] = None) -> None:
        # Prefer explicit arg → settings → default cache location
        self._weights_path: Path = (
            weights_path
            or settings.zero_dce_weights
            or _DEFAULT_WEIGHTS_CACHE
        )
        self._net = None
        self._device = None

    @property
    def is_configured(self) -> bool:
        return True  # always works — downloads weights on first use

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enhance_images(self, input_dir: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Enhance all images in input_dir.
        If output_dir is None, enhances in-place (overwrites originals).
        Returns the directory where enhanced images were written.
        """
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)

        image_files = sorted([
            f for f in input_dir.iterdir()
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ])

        if not image_files:
            print("[zero-dce] No images found — nothing to do.")
            return output_dir or input_dir

        sample = image_files[:: max(1, len(image_files) // 6)][:6]
        means = [ImageStat.Stat(Image.open(p).convert("L")).mean[0] for p in sample]
        overall_mean = sum(means) / len(means)
        print(f"[zero-dce] Mean brightness: {overall_mean:.1f}/255  ({len(image_files)} images)")

        if overall_mean >= self.DARK:
            print("[zero-dce] Images well-lit — skipping enhancement.")
            if output_dir is not None:
                import shutil
                for p in image_files:
                    shutil.copy2(p, output_dir / p.name)
        elif overall_mean < self.VERY_DARK:
            print("[zero-dce] Very dark — running Zero-DCE neural enhancement.")
            self._run_zero_dce(image_files, output_dir)
        else:
            g = math.log(self.TARGET / 255.0) / math.log(max(overall_mean, 1.0) / 255.0)
            g = max(0.4, min(g, 2.5))
            print(f"[zero-dce] Moderately dark — gamma correction γ={g:.2f}")
            self._run_gamma(image_files, output_dir, overall_mean)

        return output_dir or input_dir

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_weights(self) -> Path:
        if self._weights_path.exists():
            return self._weights_path
        self._weights_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[zero-dce] Downloading pretrained weights (~8 MB) → {self._weights_path}")
        urllib.request.urlretrieve(WEIGHTS_URL, str(self._weights_path))
        print("[zero-dce] Download complete.")
        return self._weights_path

    def _load_net(self):
        if self._net is not None:
            return self._net, self._device

        import torch
        import torch.nn as nn

        class _Net(nn.Module):
            def __init__(self):
                super().__init__()
                n = 32
                self.relu   = nn.ReLU(inplace=True)
                self.e_conv1 = nn.Conv2d(3,   n,   3, 1, 1, bias=True)
                self.e_conv2 = nn.Conv2d(n,   n,   3, 1, 1, bias=True)
                self.e_conv3 = nn.Conv2d(n,   n,   3, 1, 1, bias=True)
                self.e_conv4 = nn.Conv2d(n,   n,   3, 1, 1, bias=True)
                self.e_conv5 = nn.Conv2d(n*2, n,   3, 1, 1, bias=True)
                self.e_conv6 = nn.Conv2d(n*2, n,   3, 1, 1, bias=True)
                self.e_conv7 = nn.Conv2d(n*2, 24,  3, 1, 1, bias=True)

            def forward(self, x):
                x1 = self.relu(self.e_conv1(x))
                x2 = self.relu(self.e_conv2(x1))
                x3 = self.relu(self.e_conv3(x2))
                x4 = self.relu(self.e_conv4(x3))
                x5 = self.relu(self.e_conv5(torch.cat([x3, x4], 1)))
                x6 = self.relu(self.e_conv6(torch.cat([x2, x5], 1)))
                xr = torch.tanh(self.e_conv7(torch.cat([x1, x6], 1)))
                for r in torch.split(xr, 3, dim=1):   # 8 curve iterations
                    x = x + r * (x.pow(2) - x)
                return x

        # Pick best available device: CUDA > MPS (Apple Silicon) > CPU
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")

        weights = self._ensure_weights()
        net = _Net().to(device)
        net.load_state_dict(torch.load(str(weights), map_location=device, weights_only=False))
        net.eval()

        self._net = net
        self._device = device
        print(f"[zero-dce] Model ready on {device}")
        return net, device

    def _run_zero_dce(self, image_files: list, output_dir: Optional[Path]) -> None:
        import torch
        net, device = self._load_net()

        with torch.no_grad():
            for i, p in enumerate(image_files, 1):
                print(f"[zero-dce]   [{i}/{len(image_files)}] {p.name}")
                img = Image.open(p).convert("RGB")
                W, H = img.size
                scale = min(1.0, self.MAX_DIM / max(W, H))
                proc = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS) if scale < 1.0 else img

                arr = np.array(proc, dtype=np.float32) / 255.0
                t   = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
                out = net(t).clamp(0.0, 1.0)
                out_arr = (out.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
                enhanced = Image.fromarray(out_arr)

                if scale < 1.0:
                    enhanced = enhanced.resize((W, H), Image.LANCZOS)

                dest = (output_dir / p.name) if output_dir else p
                kw = {"quality": 95} if p.suffix.lower() in (".jpg", ".jpeg") else {}
                enhanced.save(dest, **kw)

                del t, out, out_arr
                if device.type == "cuda":
                    torch.cuda.empty_cache()

    def _run_gamma(self, image_files: list, output_dir: Optional[Path], mean: float) -> None:
        g = math.log(self.TARGET / 255.0) / math.log(max(mean, 1.0) / 255.0)
        g = max(0.4, min(g, 2.5))
        lut = bytes([min(255, int((i / 255.0) ** (1.0 / g) * 255)) for i in range(256)])
        for p in image_files:
            img = Image.open(p).convert("RGB")
            img = img.point(lut * 3)
            dest = (output_dir / p.name) if output_dir else p
            kw = {"quality": 95} if p.suffix.lower() in (".jpg", ".jpeg") else {}
            img.save(dest, **kw)
