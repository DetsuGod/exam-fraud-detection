import os
import sys
import shutil
from ultralytics import YOLO

# Configure stdout to use UTF-8 for Vietnamese characters on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    classroom_dir = os.path.join(current_dir, "images classroom")
    dataset_dir = os.path.join(current_dir, "dataset")
    
    if not os.path.exists(classroom_dir):
        print(f"[ERROR] Directory '{classroom_dir}' does not exist.")
        return
        
    print("=" * 60)
    print("   AUTOMATED EMPTY CLASSROOM IMAGE FILTER USING YOLOv8")
    print("=" * 60)
    print(f"[INFO] Source folder: {classroom_dir}")
    print(f"[INFO] Target dataset: {dataset_dir}")
    
    # Load pretrained YOLOv8 nano model
    print("[INFO] Loading YOLOv8 nano model to detect people/phones/books...")
    model_path = os.path.join(current_dir, "yolov8n.pt")
    if not os.path.exists(model_path):
        model = YOLO("yolov8n.pt") # Downloads automatically if not present
    else:
        model = YOLO(model_path)
        
    # Get list of images
    all_images = [f for f in os.listdir(classroom_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f"[INFO] Found {len(all_images)} total images in source folder.")
    
    empty_classroom_images = []
    checked_count = 0
    
    print("[PROCESS] Filtering empty classroom images (No person, phone, or book detected)...")
    for img_name in all_images:
        img_path = os.path.join(classroom_dir, img_name)
        
        # Run YOLO detection
        results = model.predict(source=img_path, conf=0.25, verbose=False)
        boxes = results[0].boxes
        
        # Check for person (0), phone (67), book (73)
        has_people_or_objects = False
        for box in boxes:
            cls = int(box.cls[0])
            if cls in [0, 67, 73]: # 0 = person, 67 = cell phone, 73 = book
                has_people_or_objects = True
                break
                
        checked_count += 1
        
        if not has_people_or_objects:
            empty_classroom_images.append(img_name)
            print(f"  -> [FOUND] Empty Classroom {len(empty_classroom_images)}/100: {img_name} (checked {checked_count})")
        
        if len(empty_classroom_images) >= 100:
            break
            
    print(f"\n[INFO] Filter complete. Found {len(empty_classroom_images)} empty classroom images after checking {checked_count} images.")
    
    if len(empty_classroom_images) < 100:
        print(f"[WARNING] Only found {len(empty_classroom_images)} empty images. We will use all of them.")
        
    # Split into Train (80%) and Val (20%)
    num_empty = len(empty_classroom_images)
    num_train = int(num_empty * 0.8)
    
    train_images = empty_classroom_images[:num_train]
    val_images = empty_classroom_images[num_train:]
    
    configs = [
        {"split": "train", "images": train_images},
        {"split": "val", "images": val_images}
    ]
    
    for cfg in configs:
        split = cfg["split"]
        images = cfg["images"]
        
        images_dest_dir = os.path.join(dataset_dir, "images", split)
        labels_dest_dir = os.path.join(dataset_dir, "labels", split)
        os.makedirs(images_dest_dir, exist_ok=True)
        os.makedirs(labels_dest_dir, exist_ok=True)
        
        print(f"\n[COPYING] Copying {len(images)} background empty classroom images for split: {split.upper()}")
        for i, img_name in enumerate(images):
            src_path = os.path.join(classroom_dir, img_name)
            
            # Destination file names
            new_img_name = f"bg_classroom_{img_name}"
            img_dest = os.path.join(images_dest_dir, new_img_name)
            
            # Label destination
            label_name = os.path.splitext(new_img_name)[0] + ".txt"
            label_dest = os.path.join(labels_dest_dir, label_name)
            
            # Copy image
            shutil.copy(src_path, img_dest)
            
            # Write empty label file
            with open(label_dest, 'w', encoding='utf-8') as lf:
                pass
                
            if (i + 1) % 10 == 0 or (i + 1) == len(images):
                print(f"  -> Copied {i+1}/{len(images)}: {new_img_name}")
                
    print("\n" + "=" * 60)
    print("   AUTOMATED FILTERING AND INGESTION COMPLETE!")
    print(f"   Successfully added {len(empty_classroom_images)} empty classroom images as backgrounds.")
    print("=" * 60)

if __name__ == "__main__":
    main()
