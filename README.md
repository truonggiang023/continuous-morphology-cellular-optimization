# Continuous morphology cellular optimization

**FEM → XGBoost / RF / SVR → SHAP → NSGA-II → Abaqus verification** cho cấu trúc cellular kim loại core-only chịu nén quasi-static.

Nghiên cứu dùng một họ kiến trúc có cùng connectivity, biến đổi liên tục conventional (`lambda_m < 0`) → transition (`0`) → re-entrant (`> 0`). Vật liệu cố định AlSi10Mg–LPBF. Đầu vào ML: `r_L ∈ [0.40, 0.60]`, `t ∈ [0.30, 0.60] mm`, `lambda_m ∈ [-1, 1]`. Cấu hình nghiên cứu tại [configs/alsi10mg.json](configs/alsi10mg.json).

Đã đối chiếu workbook `ContinuousMorphology_Dataset_A_B_v2.xlsx`: Dataset A 21 mẫu, Dataset B 300 mẫu (3 anchor + 297 LHS), thickness tham chiếu 0.30 mm. File được cung cấp hiện chưa có các kết quả FEM; các ô target đều trống.

## Cài đặt

```bash
cd /workspace/continuous-morphology-cellular-optimization
python -m venv /workspace/cmco-venv
source /workspace/cmco-venv/bin/activate
export MPLCONFIGDIR=/workspace/.cache/cmco/matplotlib
export XDG_CACHE_HOME=/workspace/.cache/cmco/xdg
export PIP_CACHE_DIR=/workspace/.cache/cmco/pip
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME" "$PIP_CACHE_DIR"
python -m pip install -r requirements.lock.txt -e '.[test]'
pytest -q
```

Lockfile ghi lại môi trường Python 3.12 Linux đã kiểm tra. XGBoost chạy CPU một luồng trong workflow này. Cloud không có Abaqus/giấy phép; chạy xuất ODB trên máy Abaqus rồi đưa CSV sang đây.

## Nhập workbook v2 đã đối chiếu

```bash
cmco-import-workbook --input /path/to/ContinuousMorphology_Dataset_A_B_v2.xlsx --output runs/workbook-import-001
cmco --data runs/workbook-import-001/fem_dataset.csv --config runs/workbook-import-001/workbook_config.json --output runs/workbook-ml-001
```

Importer giữ nguyên file Excel, tách A/B, bảo toàn DOE_ID và xuất audit theo từng dòng. Bộ import hiện tại tại `runs/workbook-v2/` có 21 mẫu A và 300 mẫu B nhưng **0 mẫu đủ điều kiện**. Vì file chưa có kết quả FEM, chỉ bước import chạy được; ML sẽ báo thiếu dữ liệu. Cần ít nhất 10 mẫu đầy đủ để phần mềm chạy, và đủ nhóm train cho CV; đây không phải tiêu chí bảo đảm độ tin cậy nghiên cứu.

Workbook đang chọn **SEA_d và PCF_preD**. Cấu hình do importer tạo lấy selector trực tiếp từ Design_Space; dùng cấu hình này cho workbook thay vì mặc định SEA_60 bên dưới. SEA trong Excel là **J/g**, importer đổi sang **J/kg bằng nhân 1000**. Không dùng lại công thức/cached target rỗng làm số 0. Các tính toán mass, SEA và QC đã biết được tính lại từ trường gốc; không chạy công thức Excel tổng quát hoặc phụ thuộc Excel để tính cache.

QC B theo file: JobStatus phải `Valid`, nominal geometry hợp lệ, actual width sai lệch không quá 0.5%, Max_ALLKE_ALLIE không quá 5%. Importer đọc width tolerance trong workbook, kiểm tra thêm khối lượng dương, target đã chọn và epsilon_d hợp lệ khi cần; giữ loại trừ UseForML nếu nhập FALSE thủ công. Các ngưỡng này là chính sách của workbook, không phải chứng nhận FEM hợp lệ. ALLAE chưa được dùng trong công thức UseForML của file. Vì summary không có thông tin cực đại eta tại biên hay đánh giá đường cong, importer ghi `densification_status=not_available_from_summary`, không tự gắn `ok`.

Giữ nguyên 300 thiết kế từ workbook để theo dõi FEM đang chạy. DOE 315 mẫu do công cụ tổng quát bên dưới tạo là một kế hoạch thay thế trước khi đọc workbook, **không phải dataset v2**.

## Chạy trực tiếp với kết quả FEM đã có

Nếu mô hình Abaqus và hậu xử lý đã có, chỉ cần bước này; các mục DOE/ODB bên dưới là tùy chọn:

```bash
cmco --data /path/to/dataset_B.csv --config configs/alsi10mg.json --output runs/ml-sea60-001
cmco --data /path/to/dataset_B.csv --config configs/alsi10mg_sead.json --output runs/ml-sead-001
```

Dùng header ở [data/templates/ml_dataset_B.csv](data/templates/ml_dataset_B.csv) để đối chiếu bảng FEM. Điền `dataset=B`, `qa_accepted=1` sau kiểm tra FEM, `densification_status=ok` sau kiểm tra epsilon_d. Đây là thông tin xác nhận từ người xử lý FEM; không điền để bỏ qua kết quả không đạt. Giữ `design_id` nhất quán cho cùng thiết kế. Đầu ra SEA dùng **J/kg**, PCF dùng **N**. Các cột target còn trống sẽ không dùng được cho lần huấn luyện tương ứng; chương trình báo lỗi thay vì tự điền nhãn. Đổi tên/map cột theo schema thực trong file v2 trước khi chạy.

Hai lệnh trên là hai nghiên cứu mục tiêu khác nhau, không phải gợi ý chọn cấu hình dựa trên điểm test tốt hơn. Chốt định nghĩa theo câu hỏi cơ học và quy tắc xử lý FEM.

## 1. Chuẩn bị Dataset A và B (tùy chọn)

```bash
cmco-doe --output runs/design-plan --n 300 --seed 42
```

Có sẵn kế hoạch ở `data/design_plans/`. Dataset A có 21 mức `lambda_m`, `r_L = 0.5`; `t` để trống vì phải giải hình học để giữ lượng vật liệu/relative density và envelope. `reference_t_mm=0.45` chỉ là giá trị tham chiếu tạm, chưa phải nghiệm hình học. Dataset B có 300 điểm Latin Hypercube và 15 điểm neo (12 tổ hợp biên và 3 trạng thái morphology tại tâm r_L/t). Tất cả ban đầu `qa_accepted=0`.

Điền kích thước, khối lượng core, đường dẫn đường cong và provenance sau khi xây dựng/chạy FEM. Không giữ nguyên dữ liệu hình học tham chiếu để thay cho các giá trị thực của mỗi mẫu. Xem [hợp đồng dữ liệu Abaqus](docs/abaqus_dataset.md).

## 2. Xuất đường cong từ Abaqus

Script hỗ trợ Abaqus Python 3 (2024+), dùng history output tại RP platen và **tổng** lực phản lực phù hợp với mô hình:

```bash
abaqus python scripts/export_abaqus_history.py --odb Job-B0001.odb --step Compression --u-region "Node ASSEMBLY.1" --rf-region "Node ASSEMBLY.1" --output B0001.csv
```

`Compression` và `Node ASSEMBLY.1` chỉ là ví dụ: phải thay bằng key thực trong ODB. Script không suy đoán RP hoặc cộng lực từ các nút tùy ý. Hai lịch sử phải đồng bộ thời gian. Mô hình phải dùng hệ mm–N–s–tonne; Abaqus không tự ghi hoặc chuyển đơn vị.

## 3. Hậu xử lý

```bash
cmco-postprocess --manifest /path/to/completed_B_manifest.csv --output runs/responses-B
```

CSV đường cong có `time,U2_mm,RF2_N`. Manifest chứa thông số hình học và đường dẫn CSV tương đối với manifest hoặc tuyệt đối. Chương trình lưu đường lực–chuyển vị, stress–strain và hiệu suất năng lượng, đồng thời xuất:

- `EA_d_J`, `SEA_d_J_kg`, `EA_60_J`, `SEA_60_J_kg`;
- `PCF_preD_N`, `first_peak_force_N`, `MCF_preD_N`, `CFE_preD`;
- `epsilon_d`, `plateau_stress_MPa`, khối lượng và cờ kiểm tra densification.

Quy đổi: `1 N mm = 0.001 J`, `1 tonne = 1000 kg`. Thiếu dữ liệu đến strain 0.60 thì SEA_60 để trống, không ngoại suy. Đường cong phải bắt đầu tại trạng thái không tải, displacement tăng đơn điệu theo trị tuyệt đối. Dữ liệu có hold/unloading cần xử lý theo quy ước nghiên cứu riêng; không tự sắp xếp hoặc bỏ điểm.

## 4. ML, giải thích và tối ưu

```bash
cmco --data runs/responses-B/fem_responses.csv --config configs/alsi10mg.json --output runs/optimization-001
```

Cấu hình nghiên cứu chỉ lấy Dataset B có `qa_accepted=1` và `densification_status=ok`. Tách 80/20 theo `design_id`; CV 5 fold và tuning chỉ trên train. XGBoost là mô hình chính, RF/SVR là benchmark. SVR chuẩn hóa cả feature và target bên trong từng fold. Kết quả holdout không dùng chọn mô hình. Có thể chọn `primary_model="best_cv"` để chọn theo CV; không đổi chính sách sau khi xem test rồi tuyên bố đó là test độc lập.

Mặc định tạm **max SEA_60, min PCF_preD**. Để đối chiếu SEA_d, tạo cấu hình riêng thay tên objective bằng `SEA_d_J_kg`, dùng output mới và ghi rõ lựa chọn cuối trong nghiên cứu. Bộ lọc densification vẫn áp dụng vì PCF_preD cần epsilon_d đáng tin cậy.

Mỗi lần chạy lưu CV RMSE, MAE/RMSE/R² holdout, split, mô hình, checksum dữ liệu, phiên bản thư viện, SHAP và đồ thị. Với mô hình cây, lưu thêm tensor interaction `[sample, feature, feature]`, biểu đồ `lambda_m × r_L` / `lambda_m × t`. Phần tử off-diagonal là một nửa đóng góp của cặp theo quy ước TreeSHAP; không đồng nhất với hệ số nhân quả. Nếu chọn SVR, chỉ có permutation SHAP, không có TreeSHAP interaction.

`pareto_predictions.csv` và biểu đồ Pareto là dự đoán surrogate. `abaqus_verification_candidates.csv` chọn hai cực trị và điểm gần ideal chuẩn hóa (heuristic, không phải nhận dạng knee point); các lựa chọn có thể trùng cùng thiết kế. Cột khoảng cách tới điểm train gần nhất và cờ nằm ngoài training box hỗ trợ kiểm tra độ phủ, **không phải ước lượng bất định**.

## 5. Kiểm thử phần mềm

```bash
python examples/generate_study_demo.py --output /tmp/cmco-synthetic
cmco-postprocess --manifest /tmp/cmco-synthetic/synthetic_manifest.csv --output /tmp/cmco-synthetic/responses
cmco --data /tmp/cmco-synthetic/responses/fem_responses.csv --config configs/alsi10mg.json --output /tmp/cmco-synthetic/ml
```

Các thư mục output phải mới. Demo có nhãn `SYNTHETIC_SOFTWARE_TEST_NOT_FEM`; cờ QA trong demo chỉ phục vụ kiểm thử. Không trộn demo vào dữ liệu nghiên cứu. Chỉ tải model joblib từ nguồn tin cậy.

## Phần cần hoàn thiện với FEM thực

Chưa có quy luật tọa độ hình học, sinh mesh, mô hình tiếp xúc, đường cong plastic AlSi10Mg hoặc tự động chạy solver. `E=69000 MPa`, `nu=0.30`, `rho=2.67e-9 tonne/mm³` là các giá trị baseline được cung cấp, chưa đủ xác định đáp ứng nghiền dẻo LPBF. Cần dữ liệu plastic/validation phù hợp; không suy diễn từ đường demo.

NSGA-II hiện chỉ có giới hạn hộp, chưa có ràng buộc chế tạo, tự giao cắt, mật độ cố định hoặc tính khả thi hình học. Dataset A phục vụ kiểm soát cơ chế và được tách khỏi huấn luyện mặc định. Phải kiểm chứng các phương án Pareto bằng Abaqus độc lập trước khi đưa ra kết luận nghiên cứu. SHAP giải thích mô hình, không chứng minh cơ chế vật lý hoặc quan hệ nhân quả.
