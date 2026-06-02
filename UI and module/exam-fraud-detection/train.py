import os
import shutil
from ultralytics import YOLO

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_yaml = os.path.join(current_dir, "dataset", "data.yaml")
    
    print("=" * 60)
    print("   BAT DAU HUAN LUYEN MO HINH YOLOv8-SMALL (TOI UU CPU)")
    print("=" * 60)
    print(f"[INFO] File cau hinh: {data_yaml}")
    
    # Khoi tao mo hinh YOLOv8 Pretrained Small
    model = YOLO("yolov8s.pt")
    
    # Tien hanh huan luyen mo hinh voi cac tham so da duoc toi uu hoa cho CPU
    results = model.train(
        data=data_yaml,
        epochs=15,       # 15 epochs la du de transfer learning tren dataset nho
        imgsz=416,       # Giup tang toc do train len 2.3 lan tren CPU
        batch=16
    )
    
    # Lay thu muc luu ket qua tu model.trainer.save_dir
    save_dir = str(model.trainer.save_dir)
    print(f"[INFO] Thu muc luu ket qua: {save_dir}")
    
    # Tien hanh bien dich va xuat ban sang ONNX Runtime
    print("[INFO] Dang xuat ban mo hinh sang dinh dang ONNX...")
    onnx_path = model.export(format="onnx")
    print(f"[INFO] Xuat ban ONNX thanh cong tai: {onnx_path}")
    
    # Sao chep file best.pt va best.onnx ve thu muc goc
    best_pt_src = os.path.join(save_dir, "weights", "best.pt")
    best_onnx_src = os.path.join(save_dir, "weights", "best.onnx")
    
    best_pt_dest = os.path.join(current_dir, "best.pt")
    best_onnx_dest = os.path.join(current_dir, "best.onnx")
    
    print("[INFO] Dang sao chep trong so ve thu muc goc...")
    if os.path.exists(best_pt_src):
        shutil.copy(best_pt_src, best_pt_dest)
        print(f"[INFO] Da copy best.pt ve thu muc goc: {best_pt_dest}")
    
    if os.path.exists(best_onnx_src):
        shutil.copy(best_onnx_src, best_onnx_dest)
        print(f"[INFO] Da copy best.onnx ve thu muc goc: {best_onnx_dest}")
        
    print("=" * 60)
    print("   HUAN LUYEN VA BIEN DICH ONNX HOAN TAT THANH CONG!")
    print("=" * 60)

if __name__ == "__main__":
    main()
