#!/usr/bin/env python3
"""
Enhance low-light accident photos using Zero-DCE.

Usage
-----
Enhance a local directory (in-place):
    python enhance_photos.py --dir /path/to/photos

Enhance to a separate output folder:
    python enhance_photos.py --dir /path/to/photos --out /path/to/enhanced

Download from R2, enhance, re-upload (overwrites originals):
    python enhance_photos.py --claim "Nimal Silva - 200123456789"

Download from R2, enhance, save locally (no upload):
    python enhance_photos.py --claim "Nimal Silva - 200123456789" --out /path/to/local

Thresholds (mean pixel brightness out of 255):
  < 60  → Zero-DCE  (deep-learning, best quality)
  < 100 → gamma correction  (fast, natural tone curve)
  ≥ 100 → skip  (well-lit)
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

# Run from the backend/ directory so app.* imports resolve
sys.path.insert(0, str(Path(__file__).parent))

from app.services.zero_dce import ZeroDCEService


def enhance_local(args):
    if not args.dir.is_dir():
        sys.exit(f"Error: {args.dir} is not a directory")
    svc = ZeroDCEService()
    out = svc.enhance_images(args.dir, args.out)
    print(f"\nDone. Enhanced images in: {out}")


def enhance_from_r2(args):
    from app.config import settings
    from app.services.r2 import R2Service

    folder = args.claim.strip()
    if " - " not in folder:
        sys.exit('Error: --claim must be in "Customer Name - NIC[ - timestamp]" format')

    r2 = R2Service()
    if not r2.is_configured:
        sys.exit("Error: R2 credentials not configured. Check your .env file.")

    tmpdir = Path(tempfile.mkdtemp(prefix="zerodce_"))
    images_dir = tmpdir / "images"

    try:
        print(f"Downloading photos for '{folder}' from R2…")
        downloaded = r2.download_accident_images(folder, images_dir)
        print(f"Downloaded {len(downloaded)} images.")

        svc = ZeroDCEService()

        if args.out:
            # Enhance to local output dir — no upload
            svc.enhance_images(images_dir, args.out)
            print(f"\nDone. Enhanced images saved to: {args.out}")
        else:
            # Enhance in-place then re-upload to R2
            svc.enhance_images(images_dir)

            import boto3
            from botocore.config import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
            prefix = f"{folder}/step-1-photos-uploaded/"
            print(f"\nRe-uploading enhanced images to R2 ({prefix})…")
            for f in sorted(images_dir.glob("*")):
                s3.upload_file(str(f), settings.r2_bucket_name, f"{prefix}{f.name}")
                print(f"  ✓ {f.name}")
            print("Done.")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Zero-DCE low-light photo enhancer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dir", type=Path, metavar="PATH",
                       help="Local directory of images to enhance")
    group.add_argument("--claim", type=str, metavar="'Name - NIC'",
                       help="Claim folder name — downloads from R2, enhances, re-uploads")
    parser.add_argument("--out", type=Path, metavar="PATH",
                        help="Output directory (default: in-place for --dir, re-upload for --claim)")

    args = parser.parse_args()

    if args.dir:
        enhance_local(args)
    else:
        enhance_from_r2(args)


if __name__ == "__main__":
    main()
