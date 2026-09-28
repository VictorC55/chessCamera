"""Fine-tune a YOLO pose model to find the 4 board corners.

Usage: python train.py path/to/roboflow-export-folder [epochs]
Run prep_dataset.py on the folder first.
Use weights/last_recal.pt from the run folder, not best.pt (see recalibrate_bn).
"""
import sys
from pathlib import Path
import cv2
import torch
import yaml
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox
from corner_error import corner_errors

IMGSZ = 960  # corners are small and precise; 640 loses pixels you need


def recalibrate_bn(weights, image_dir, imgsz):
    """Recompute BatchNorm running stats from the un-augmented training photos.

    With only ~5 batches per epoch the saved running stats lag far behind the
    weights, so eval mode (validation and inference) gives confident garbage even
    when the model itself is good. On a 25-epoch test this took pose mAP50-95 from
    0.17 to 0.98 for the same weights.
    """
    ck = torch.load(weights, weights_only=False)
    key = "ema" if ck.get("ema") is not None else "model"
    model = ck[key].float()
    paths = sorted(p for p in Path(image_dir).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    imgs = [LetterBox((imgsz, imgsz))(image=cv2.imread(str(p))) for p in paths]
    x = torch.stack([torch.from_numpy(im[..., ::-1].copy()).permute(2, 0, 1).float() / 255 for im in imgs])

    bns = [m for m in model.modules() if isinstance(m, torch.nn.BatchNorm2d)]
    for bn in bns:
        bn.reset_running_stats()
        bn.momentum = None  # plain average over every batch below
    model.train()
    with torch.no_grad():
        for i in range(0, len(x), 8):
            model(x[i:i + 8])
    for bn in bns:
        bn.momentum = 0.03  # Ultralytics' default, in case this file is fine-tuned again

    ck[key] = model.eval().half()
    out = Path(weights).with_name("last_recal.pt")
    torch.save(ck, out)
    return out


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    data = str(root / "data.yaml")
    epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    # the old zero-mAP collapse was stale BN stats, not MPS, but MPS hasn't been re-tested since; CPU is ~1 min/epoch
    device = 0 if torch.cuda.is_available() else "cpu"

    model = YOLO("yolo11s-pose.pt")  # COCO-pretrained; the head is rebuilt for 4 keypoints

    model.train(
        data=data,
        epochs=epochs,
        imgsz=IMGSZ,
        batch=8,          # drop to 4 if memory is tight (then also set nbs to match)
        nbs=8,            # update weights every batch; the default 64 gives ~0.6 updates/epoch on 39 photos
        device=device,
        cache="ram",      # photos are ~2500x3500; decode + resize once instead of every epoch
        patience=0,       # no early stopping: val scores read ~0 for the first ~15 epochs (stale BN), then recover
        fliplr=0.0,       # a mirror moves corner 0 (leftmost) to the rightmost spot; no fixed swap fixes that
        flipud=0.0,
        mosaic=0.3,       # board fills the frame, so heavy mosaic crops corners away
        degrees=10,       # small rotations only; large ones change which corner is leftmost
        scale=0.4,
        hsv_v=0.5,        # lighting variation, cheaper than shooting more photos
        project=str(Path(__file__).resolve().parent / "runs"),
        name="corners",
    )

    save_dir = model.trainer.save_dir
    cfg = yaml.safe_load(Path(data).read_text())
    recal = recalibrate_bn(save_dir / "weights" / "last.pt", Path(cfg["path"]) / cfg["train"], IMGSZ)
    metrics = YOLO(recal).val(data=data, imgsz=IMGSZ, device=device, project=str(save_dir), name="val_recal")

    print("\ncorner error on the validation photos (recalibrated weights):")
    corner_errors(recal, root, "valid", IMGSZ, device)

    print(f"\nresults:      {save_dir}")
    print(f"use weights:  {recal}")
    print(f"recalibrated: box mAP50 {metrics.box.map50:.3f}, pose mAP50 {metrics.pose.map50:.3f}, "
          f"pose mAP50-95 {metrics.pose.map:.3f}  (plots in {metrics.save_dir})")
