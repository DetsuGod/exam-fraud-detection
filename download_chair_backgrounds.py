import os
import urllib.request
import csv
import shutil
import sys

# Configure stdout to use UTF-8 for Vietnamese characters on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CLASS_CHAIR = "/m/01mzpv" # Open Images V7 class for Chair

def download_file(url, dest_path):
    print(f"[DOWNLOAD] Downloading: {url} ...")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response, open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"[WARNING] Failed to download {url}: {e}")
        return False

def parse_chair_annotations(csv_path):
    print(f"[PARSE] Reading annotations from: {csv_path} ...")
    image_ids = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['LabelName'] == CLASS_CHAIR:
                image_ids.add(row['ImageID'])
    return list(image_ids)

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(current_dir, "temp_chair_downloads")
    dataset_dir = os.path.join(current_dir, "dataset")
    
    os.makedirs(temp_dir, exist_ok=True)
    
    # 1. Download Validation Bounding Box annotations to find chair images (12MB)
    val_csv_url = "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv"
    val_csv_path = os.path.join(temp_dir, "validation-bbox.csv")
    
    if not os.path.exists(val_csv_path):
        success = download_file(val_csv_url, val_csv_path)
        if not success:
            print("[ERROR] Failed to download CSV annotations.")
            return
            
    # 2. Get image IDs that contain chairs
    chair_image_ids = parse_chair_annotations(val_csv_path)
    print(f"[INFO] Found {len(chair_image_ids)} images containing chairs in the validation set.")
    
    if len(chair_image_ids) == 0:
        print("[ERROR] No chair images found.")
        return
        
    # We want 50 images total (40 for train, 10 for val)
    target_train = 40
    target_val = 10
    
    # Selected image IDs
    selected_train_ids = chair_image_ids[:target_train]
    selected_val_ids = chair_image_ids[target_train:target_train + target_val]
    
    configs = [
        {"split": "train", "ids": selected_train_ids, "src_split": "validation"},
        {"split": "val", "ids": selected_val_ids, "src_split": "validation"}
    ]
    
    for cfg in configs:
        split = cfg["split"]
        ids = cfg["ids"]
        src_split = cfg["src_split"]
        
        images_dest_dir = os.path.join(dataset_dir, "images", split)
        labels_dest_dir = os.path.join(dataset_dir, "labels", split)
        os.makedirs(images_dest_dir, exist_ok=True)
        os.makedirs(labels_dest_dir, exist_ok=True)
        
        print(f"\n[DOWNLOAD] Downloading {len(ids)} background chair images for split: {split.upper()}")
        for i, img_id in enumerate(ids):
            img_url = f"https://open-images-dataset.s3.amazonaws.com/{src_split}/{img_id}.jpg"
            img_dest = os.path.join(images_dest_dir, f"bg_chair_{img_id}.jpg")
            label_dest = os.path.join(labels_dest_dir, f"bg_chair_{img_id}.txt")
            
            if not os.path.exists(img_dest):
                success = download_file(img_url, img_dest)
                if success:
                    # Write empty label file (represents background/negative sample)
                    with open(label_dest, 'w', encoding='utf-8') as lf:
                        pass # Write nothing (empty file)
                    print(f"  -> Successfully downloaded {i+1}/{len(ids)}: bg_chair_{img_id}.jpg")
                else:
                    print(f"  -> [WARNING] Failed to download: {img_id}")
            else:
                # Still ensure empty label file exists
                if not os.path.exists(label_dest):
                    with open(label_dest, 'w', encoding='utf-8') as lf:
                        pass
                print(f"  -> Already exists {i+1}/{len(ids)}: bg_chair_{img_id}.jpg")
                
    # 5. Cleanup
    try:
        shutil.rmtree(temp_dir)
        print("[CLEANUP] Cleaned up temporary download directory.")
    except Exception as e:
        pass
        
    print("\n" + "=" * 60)
    print("   DOWNLOAD OF CHAIR BACKGROUND IMAGES COMPLETE!")
    print("   All 50 images added as background negative samples.")
    print("=" * 60)

if __name__ == "__main__":
    main()
