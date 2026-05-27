from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "data" / "traffic_images"
MODEL_PATH = PROJECT_ROOT / "models" / "custom_cnn" / "traffic_cnn.pt"
CLASS_NAMES = ["clear", "moderate", "heavy", "gridlock"]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def count_images(folder: Path) -> int:
    return sum(1 for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def validate_split(split_name: str) -> dict[str, int]:
    split_dir = DATASET_DIR / split_name
    if not split_dir.exists():
        raise FileNotFoundError(f"Missing dataset split folder: {split_dir}")

    counts: dict[str, int] = {}
    for class_name in CLASS_NAMES:
        class_dir = split_dir / class_name
        if not class_dir.exists():
            raise FileNotFoundError(f"Missing class folder: {class_dir}")
        counts[class_name] = count_images(class_dir)

    if sum(counts.values()) == 0:
        raise ValueError(
            f"No images found in {split_dir}. Add labeled images under "
            f"{split_dir / CLASS_NAMES[0]} and the other class folders first."
        )

    return counts


def write_dataset_summary(path: Path, train_counts: dict[str, int], val_counts: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["split", "class_name", "image_count"])
        for split_name, counts in {"train": train_counts, "val": val_counts}.items():
            for class_name in CLASS_NAMES:
                writer.writerow([split_name, class_name, counts[class_name]])


def main() -> None:
    import torch
    from torch import nn, optim
    from torch.utils.data import DataLoader
    from torchvision import datasets, models, transforms

    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.15, contrast=0.15),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    val_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    train_counts = validate_split("train")
    val_counts = validate_split("val")
    write_dataset_summary(DATASET_DIR / "dataset_summary.csv", train_counts, val_counts)
    print("Dataset summary:")
    for class_name in CLASS_NAMES:
        print(f"  train/{class_name}: {train_counts[class_name]}")
    for class_name in CLASS_NAMES:
        print(f"  val/{class_name}: {val_counts[class_name]}")

    train_data = datasets.ImageFolder(DATASET_DIR / "train", transform=transform)
    val_data = datasets.ImageFolder(DATASET_DIR / "val", transform=val_transform)

    train_loader = DataLoader(train_data, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=16)

    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(CLASS_NAMES))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=0.0003)

    for epoch in range(8):
        model.train()
        total_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())

        model.eval()
        correct = 0
        count = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                predictions = torch.argmax(model(images), dim=1)
                correct += int((predictions == labels).sum().item())
                count += int(labels.numel())

        accuracy = correct / max(count, 1)
        print(f"Epoch {epoch + 1}: loss={total_loss:.3f} val_accuracy={accuracy:.2%}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model, MODEL_PATH)
    print(f"Saved custom CNN to {MODEL_PATH}")


if __name__ == "__main__":
    main()
