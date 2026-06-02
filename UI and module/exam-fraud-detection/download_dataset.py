import os
import sys
import urllib.request
import csv
import shutil

# Cau hinh các lop va ID cua Open Images
# Mobile phone -> /m/050k8
# Book -> /m/01n5w
CLASS_MAPPING = {
    "/m/050k8": 0,  # Mobile phone
    "/m/01n5w": 1   # Book
}

CLASS_NAMES = {
    0: "Mobile phone",
    1: "Book"
}

def download_file(url, dest_path):
    print(f"[DOWNLOAD] Dang tai: {url} ...")
    try:
        # Them User-Agent de tranh bi chan bieu tuong chan bot
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response, open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"[WARNING] Khong the tai file {url}: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False

def parse_annotations(csv_path):
    print(f"[PARSE] Dang doc nhan tu file: {csv_path} ...")
    annotations_by_image = {}
    
    # Doc tung dong bang luong de tiep kiem RAM tuyet doi
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            label_name = row['LabelName']
            if label_name in CLASS_MAPPING:
                image_id = row['ImageID']
                class_id = CLASS_MAPPING[label_name]
                
                # YOLO format yeu cau toa do chuan hoa: x_center, y_center, width, height
                xmin = float(row['XMin'])
                xmax = float(row['XMax'])
                ymin = float(row['YMin'])
                ymax = float(row['YMax'])
                
                x_center = (xmin + xmax) / 2.0
                y_center = (ymin + ymax) / 2.0
                width = xmax - xmin
                height = ymax - ymin
                
                if image_id not in annotations_by_image:
                    annotations_by_image[image_id] = []
                
                annotations_by_image[image_id].append({
                    "class_id": class_id,
                    "bbox": [x_center, y_center, width, height]
                })
                
    return annotations_by_image

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(current_dir, "dataset_temp")
    dataset_dir = os.path.join(current_dir, "dataset")
    
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(dataset_dir, exist_ok=True)
    
    print("=" * 60)
    print("   BO TAI DATASET GOOGLE OPEN IMAGES V7 CHO YOLOv8")
    print("=" * 60)
    print(f"[INFO] Lop hoc can tai: {list(CLASS_NAMES.values())}")
    print(f"[INFO] Thu muc luu dataset: {dataset_dir}")
    
    # 1. Tai cac file CSV annotation (nhe hon rat nhieu tap Train)
    # Validation annotations (12MB) -> dung de lam tap VAL
    # Test annotations (36MB) -> dung de lam tap TRAIN (de nhanh va du anh)
    val_csv_url = "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv"
    train_csv_url = "https://storage.googleapis.com/openimages/v5/test-annotations-bbox.csv"
    
    val_csv_path = os.path.join(temp_dir, "validation-bbox.csv")
    train_csv_path = os.path.join(temp_dir, "test-bbox.csv")
    
    if not os.path.exists(val_csv_path):
        download_file(val_csv_url, val_csv_path)
    if not os.path.exists(train_csv_path):
        download_file(train_csv_url, train_csv_path)
        
    # 2. Parse thong tin annotations
    val_annos = parse_annotations(val_csv_path)
    train_annos = parse_annotations(train_csv_path)
    
    # 3. Tai ảnh và tạo nhãn YOLO
    # Cấu hình số lượng ảnh cần tải cho từng lớp
    configs = [
        {
            "split": "train",
            "annos": train_annos,
            "img_src_split": "test", # Lay anh tu folder test cua GCS
            "target_per_class": 150  # 150 anh phone + 150 anh book
        },
        {
            "split": "val",
            "annos": val_annos,
            "img_src_split": "validation", # Lay anh tu folder validation cua GCS
            "target_per_class": 30   # 30 anh phone + 30 anh book
        }
    ]
    
    for cfg in configs:
        split = cfg["split"]
        annos = cfg["annos"]
        img_src_split = cfg["img_src_split"]
        target = cfg["target_per_class"]
        
        print("\n" + "-" * 50)
        print(f"[PROCESS] Dang tai va bien dich tap [{split.upper()}] ...")
        print("-" * 50)
        
        # Tao thu muc images/labels tuong ung
        images_dest_dir = os.path.join(dataset_dir, "images", split)
        labels_dest_dir = os.path.join(dataset_dir, "labels", split)
        os.makedirs(images_dest_dir, exist_ok=True)
        os.makedirs(labels_dest_dir, exist_ok=True)
        
        # Phân loại ImageIDs theo các nhãn
        class_images = {0: [], 1: []}
        for img_id, items in annos.items():
            for item in items:
                c_id = item["class_id"]
                if img_id not in class_images[c_id]:
                    class_images[c_id].append(img_id)
                    
        # Chon danh sach ImageIDs doc lap de download
        selected_images = set()
        for c_id in [0, 1]:
            count = 0
            for img_id in class_images[c_id]:
                if count >= target:
                    break
                selected_images.add(img_id)
                count += 1
                
        print(f"[INFO] Tong so anh can tai cho tap [{split.upper()}]: {len(selected_images)}")
        
        # Bat dau tai tung anh va ghi file label .txt tuong ung
        downloaded_count = 0
        for idx, img_id in enumerate(selected_images):
            img_url = f"https://open-images-dataset.s3.amazonaws.com/{img_src_split}/{img_id}.jpg"
            img_dest = os.path.join(images_dest_dir, f"{img_id}.jpg")
            label_dest = os.path.join(labels_dest_dir, f"{img_id}.txt")
            
            # Neu da co anh thi bo qua tai
            success = True
            if not os.path.exists(img_dest):
                success = download_file(img_url, img_dest)
                
            if success:
                # Ghi file label theo format YOLO
                with open(label_dest, 'w', encoding='utf-8') as lf:
                    for item in annos[img_id]:
                        c_id = item["class_id"]
                        bbox = item["bbox"]
                        lf.write(f"{c_id} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}\n")
                
                downloaded_count += 1
                if downloaded_count % 10 == 0 or downloaded_count == len(selected_images):
                    print(f"[PROGRESS] Da chuan bi xong: {downloaded_count}/{len(selected_images)} anh.")
            else:
                print(f"[WARNING] Bo qua anh {img_id} do tai loi.")

    # 4. Ghi file data.yaml cho YOLOv8
    data_yaml_path = os.path.join(dataset_dir, "data.yaml")
    print(f"\n[EXPORT] Dang ghi file cau hinh YOLO: {data_yaml_path}...")
    
    dataset_dir_cleaned = dataset_dir.replace('\\', '/')
    yaml_content = f"""# Cấu hình tập dữ liệu giám sát cho YOLOv8
path: {dataset_dir_cleaned} # Đường dẫn thư mục gốc tuyệt đối
train: images/train                   # Thư mục ảnh huấn luyện
val: images/val                       # Thư mục ảnh xác thực

# Nhãn các lớp nhận diện (Class Labels)
names:
  0: Mobile phone
  1: Book
"""
    with open(data_yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    # Xoa thu muc cache tam thoi de tiet kiem RAM va o cung
    try:
        shutil.rmtree(temp_dir)
        print("[CLEANUP] Da xoa thu muc cache tam thoi.")
    except Exception as e:
        pass
        
    print("=" * 60)
    print("   HOAN THANH TAI VA CHUAN BI TAP DU LIEU!")
    print("=" * 60)
    print(f"Dataset cua ban da san sang tai thu muc: {dataset_dir}")
    print("De bat dau huan luyen mo hinh YOLOv8 tren tap du lieu nay, hay chay lenh sau:")
    print(f"\n   yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=50 imgsz=640 batch=16")
    print("=" * 60)

if __name__ == "__main__":
    main()
