import os
import sys
import shutil
import random

# Configure stdout to use UTF-8 for Vietnamese characters on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    phone_data_dir = os.path.join(current_dir, "mobile phone data")
    student_data_dir = os.path.join(current_dir, "student in class dataset")
    dataset_dir = os.path.join(current_dir, "dataset")
    
    # 1. Verify source folders
    if not os.path.exists(phone_data_dir):
        print(f"[ERROR] Mobile phone data directory '{phone_data_dir}' not found.")
        return
    if not os.path.exists(student_data_dir):
        print(f"[ERROR] Student in class dataset directory '{student_data_dir}' not found.")
        return
        
    print("=" * 60)
    print("   CUSTOM DATASET MERGER & DATA INGESTION UTILITY")
    print("=" * 60)
    print(f"[INFO] Mobile phone data: {phone_data_dir}")
    print(f"[INFO] Student in class data: {student_data_dir}")
    print(f"[INFO] Target YOLO dataset: {dataset_dir}")
    
    random.seed(42) # For reproducible splits
    
    # ----------------------------------------------------
    # PHASE 1: Merge Mobile Phone Dataset (Positive Samples)
    # ----------------------------------------------------
    print("\n[PHASE 1] Merging Mobile Phone Dataset (Class 0: Mobile phone)...")
    phone_img_src = os.path.join(phone_data_dir, "train", "images")
    phone_lbl_src = os.path.join(phone_data_dir, "train", "labels")
    
    if not os.path.exists(phone_img_src) or not os.path.exists(phone_lbl_src):
        print(f"[ERROR] Source subfolders in '{phone_data_dir}' not found.")
        return
        
    phone_images = [f for f in os.listdir(phone_img_src) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f"[INFO] Found {len(phone_images)} phone images.")
    
    # Shuffle and split (85% Train, 15% Val)
    random.shuffle(phone_images)
    num_phone = len(phone_images)
    num_phone_train = int(num_phone * 0.85)
    
    phone_train_set = phone_images[:num_phone_train]
    phone_val_set = phone_images[num_phone_train:]
    
    phone_configs = [
        {"split": "train", "images": phone_train_set},
        {"split": "val", "images": phone_val_set}
    ]
    
    copied_phones = 0
    for cfg in phone_configs:
        split = cfg["split"]
        images = cfg["images"]
        
        img_dest_dir = os.path.join(dataset_dir, "images", split)
        lbl_dest_dir = os.path.join(dataset_dir, "labels", split)
        os.makedirs(img_dest_dir, exist_ok=True)
        os.makedirs(lbl_dest_dir, exist_ok=True)
        
        for img_name in images:
            # Source paths
            src_img_path = os.path.join(phone_img_src, img_name)
            base_name = os.path.splitext(img_name)[0]
            src_lbl_path = os.path.join(phone_lbl_src, base_name + ".txt")
            
            if not os.path.exists(src_lbl_path):
                continue
                
            # Dest paths with prefix to prevent collisions
            dest_img_name = f"phone_rf_{img_name}"
            dest_lbl_name = f"phone_rf_{base_name}.txt"
            
            dest_img_path = os.path.join(img_dest_dir, dest_img_name)
            dest_lbl_path = os.path.join(lbl_dest_dir, dest_lbl_name)
            
            # Copy image and label
            shutil.copy(src_img_path, dest_img_path)
            shutil.copy(src_lbl_path, dest_lbl_path)
            copied_phones += 1
            
    print(f"[SUCCESS] Merged {copied_phones} phone images and labels into dataset.")
    
    # ----------------------------------------------------
    # PHASE 2: Merge Student Dataset (Background/Negative Samples)
    # ----------------------------------------------------
    print("\n[PHASE 2] Merging Student Dataset as Background Negative Samples...")
    student_img_src = os.path.join(student_data_dir, "train", "images")
    
    if not os.path.exists(student_img_src):
        print(f"[ERROR] Source images folder in '{student_data_dir}' not found.")
        return
        
    student_images = [f for f in os.listdir(student_img_src) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f"[INFO] Found {len(student_images)} student classroom images.")
    
    # Shuffle and split (85% Train, 15% Val)
    random.shuffle(student_images)
    num_student = len(student_images)
    num_student_train = int(num_student * 0.85)
    
    student_train_set = student_images[:num_student_train]
    student_val_set = student_images[num_student_train:]
    
    student_configs = [
        {"split": "train", "images": student_train_set},
        {"split": "val", "images": student_val_set}
    ]
    
    copied_students = 0
    for cfg in student_configs:
        split = cfg["split"]
        images = cfg["images"]
        
        img_dest_dir = os.path.join(dataset_dir, "images", split)
        lbl_dest_dir = os.path.join(dataset_dir, "labels", split)
        os.makedirs(img_dest_dir, exist_ok=True)
        os.makedirs(lbl_dest_dir, exist_ok=True)
        
        for img_name in images:
            src_img_path = os.path.join(student_img_src, img_name)
            base_name = os.path.splitext(img_name)[0]
            
            # Dest paths with prefix to prevent collisions
            dest_img_name = f"student_rf_{img_name}"
            dest_lbl_name = f"student_rf_{base_name}.txt"
            
            dest_img_path = os.path.join(img_dest_dir, dest_img_name)
            dest_lbl_path = os.path.join(lbl_dest_dir, dest_lbl_name)
            
            # Copy image
            shutil.copy(src_img_path, dest_img_path)
            
            # Create EMPTY label file (Negative sample)
            with open(dest_lbl_path, 'w', encoding='utf-8') as lf:
                pass
                
            copied_students += 1
            
    print(f"[SUCCESS] Merged {copied_students} student classroom images as background samples.")
    print("\n" + "=" * 60)
    print("   DATASET INTEGRATION & MERGING COMPLETED!")
    print("   Both datasets are successfully processed and integrated.")
    print("=" * 60)

if __name__ == "__main__":
    main()
