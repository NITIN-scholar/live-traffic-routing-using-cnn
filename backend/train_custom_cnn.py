from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "data" / "traffic_images"
MODEL_PATH = PROJECT_ROOT / "models" / "custom_cnn" / "traffic_cnn.pt"
CLASS_NAMES = ["clear", "moderate", "heavy", "gridlock"]


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
