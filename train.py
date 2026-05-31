import os
import shutil
import sys
from ultralytics import YOLO

# Configure stdout to use UTF-8 for Vietnamese characters on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_yaml = os.path.join(current_dir, "dataset", "data.yaml")
    
    print("=" * 60)
    print("   BAT DAU HUAN LUYEN MO HINH YOLOv8-SMALL (TOI UU CPU)")
    print("=" * 60)
    print(f"[INFO] File cau hinh: {data_yaml}")
    
    # Khoi tao mo hinh YOLOv8 Pretrained Nano (Nhe hon & nhanh hon tren CPU)
    model = YOLO("yolov8n.pt")
    
    # Tien hanh huan luyen mo hinh voi cac tham so toi uu hoa cho YOLOv8 Nano tren CPU
    results = model.train(
        data=data_yaml,
        epochs=25,          # tang len 25 epochs de mo hinh dat chat luong cao nhat
        imgsz=512,          # Giup nhan dien vat nho (dien thoai, sach) tot nhat
        batch=16,           # Batch size toi uu
        optimizer='AdamW',  # Optimizer hien dai giup on dinh trong so
        lr0=0.002,          # Learning rate khoi dau toi uu cho transfer learning
        cos_lr=True,        # Giam cuong do hoc muot ma
        close_mosaic=5,     # Tat mosaic augmentation trong 5 epochs cuoi de tinh chinh o bao chinh xac
        degrees=10.0,       # Xoay anh nhe
        translate=0.1,      # Dich chuyen anh nhe de tang tinh tong quat
        scale=0.5,          # Thu phong ngau nhien
        fliplr=0.5,         # Lat ngang anh ngau nhien
        verbose=True
    )
    
    # Lay thu muc luu ket qua tu model.trainer.save_dir
    save_dir = str(model.trainer.save_dir)
    print(f"[INFO] Thu muc luu ket qua: {save_dir}")
    
    # Sao chep file best.pt ve thu muc goc
    best_pt_src = os.path.join(save_dir, "weights", "best.pt")
    best_pt_dest = os.path.join(current_dir, "best.pt")
    
    print("[INFO] Dang sao chep trong so ve thu muc goc...")
    if os.path.exists(best_pt_src):
        shutil.copy(best_pt_src, best_pt_dest)
        print(f"[INFO] Da copy best.pt ve thu muc goc: {best_pt_dest}")
        
    print("=" * 60)
    print("   HUAN LUYEN HOAN TAT THANH CONG!")
    print("=" * 60)

if __name__ == "__main__":
    main()
