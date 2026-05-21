# Tong hop cap nhat chuc nang

Ngay cap nhat: 17/05/2026

## 1. Lien ket chung tu theo tung nghiep vu chi phi

Da bo sung co che lien ket chung tu va file dinh kem truc tiep voi tung nghiep vu chi phi thong qua truong `expense_id`.

Nhung diem da co:

- Khi them chung tu, nguoi dung phai chon nghiep vu chi phi lien quan.
- Tu man hinh Chi phi co nut "Them chung tu cho chi phi" de gan chung tu vao dung dong chi phi dang chon.
- Co nut "Gan file theo chi phi" de dinh kem file chung tu vao tung nghiep vu.
- Bang Chi phi hien them so luong chung tu va so luong file da gan.
- Bang Hoa don/Chung tu hien them cot "Chi phi ID" de tra nguoc ve nghiep vu chi phi.

File chinh da sua:

- `modules/invoices.py`
- `modules/accounting.py`
- `ui/main_window.py`
- `ui/dialogs.py`
- `database/__init__.py`

## 2. Danh muc mac dinh cho form Them chi phi

Da sua form Them chi phi de dropdown Du an va Loai chi phi co du lieu mac dinh, de nguoi dung click chon thay vi khong co noi dung.

Du an mac dinh:

- CHUNG - Chi phi chung cong ty
- CT001 - Cong trinh mau 01

Danh muc chi phi mac dinh:

- Vat lieu xay dung
- Vat tu phu
- Nhan cong
- Thau phu
- May thi cong
- Van chuyen
- Quan ly cong trinh
- Van phong
- Tam ung
- Chi phi khac

Dong thoi da sua loi luu sai ID khi combobox hien thi dang `1 - Ten noi dung`. He thong bay gio tach dung ID de luu vao database.

## 3. He thong quy dinh va quy trinh ho so

Da them man hinh moi tren menu:

`Quy dinh`

Chuc nang:

- Tra cuu quy dinh/quy trinh theo loai chi phi hoac nghiep vu.
- Hien thi ho so can co.
- Hien thi canh bao rui ro neu thieu chung tu.
- Hien thi can cu phap ly/noi bo.

Quy dinh mac dinh da them:

- Ho so mua vat lieu xay dung
- Ho so nhan cong
- Ho so thau phu
- Ho so may thi cong
- Ho so van chuyen
- Ho so tam ung/hoan ung
- Ho so chi phi khac

Khi them chi phi moi, neu loai chi phi co quy dinh tuong ung, phan mem se hien canh bao ho so can co.

File moi:

- `modules/compliance.py`

Bang database moi:

- `compliance_rules`

## 4. He thong tai khoan ke toan theo Thong tu 99/2025/TT-BTC

Da them man hinh moi tren menu:

`Tai khoan`

Chuc nang:

- Tra cuu tai khoan theo so hieu, ten, loai tai khoan hoac mo ta.
- Hien thi danh muc tai khoan ke toan.
- Luu can cu la Thong tu 99/2025/TT-BTC, Phu luc II - He thong tai khoan ke toan doanh nghiep.

Da seed 44 tai khoan pho bien, gom cac nhom:

- Tien va tuong duong tien: 111, 112, 113
- Phai thu, tam ung: 131, 133, 136, 138, 141
- Hang ton kho, chi phi do dang: 151, 152, 153, 154, 155, 156
- Tai san co dinh va xay dung co ban: 211, 213, 214, 241, 242
- Phai tra va no vay: 331, 333, 334, 335, 338, 341
- Von chu so huu: 411, 421
- Doanh thu: 511, 515, 521
- Chi phi san xuat/xay lap: 621, 622, 623, 627
- Chi phi va ket qua kinh doanh: 632, 635, 641, 642, 711, 811, 821, 911

Luu y: danh muc hien tai la bo tai khoan nen de dua vao phan mem va tra cuu nhanh. Neu can dung chuan day du theo tung tieu khoan cap 2/cap 3 cua doanh nghiep, can tiep tuc bo sung chi tiet theo phu luc chinh thuc va quy che ke toan noi bo.

## 5. Database migration

Da bo sung migration de database cu van chay duoc, khong can xoa file `accounting.db`.

Cot moi:

- `documents.expense_id`
- `documents.updated_at`
- `attachments.expense_id`
- `accounts.account_level`
- `accounts.parent_code`
- `accounts.legal_basis`
- `accounts.active`

Bang moi:

- `compliance_rules`

Da chay khoi tao database thanh cong.

Ket qua kiem tra:

- Projects: 2
- Expense categories: 10
- Compliance rules: 7
- Accounts: 44

## 6. Cach su dung nhanh

### Them chi phi

1. Vao menu `Chi phi`.
2. Bam `Them chi phi`.
3. Chon Du an va Loai chi phi tu danh sach co san.
4. Nhap mo ta, so tien, nguoi chi, hinh thuc thanh toan.
5. Bam Luu.
6. Neu loai chi phi co quy dinh ho so, phan mem se canh bao chung tu can co.

### Gan chung tu vao chi phi

1. Vao menu `Chi phi`.
2. Chon dong chi phi can gan chung tu.
3. Bam `Them chung tu cho chi phi`.
4. Nhap thong tin chung tu va luu.

### Gan file vao chi phi

1. Vao menu `Chi phi`.
2. Chon dong chi phi.
3. Bam `Gan file theo chi phi`.
4. Chon file can dinh kem.

### Tra cuu ho so can co

1. Vao menu `Quy dinh`.
2. Nhap tu khoa can tim, vi du: vat lieu, nhan cong, thau phu.
3. Xem cot Ho so can co va Canh bao.

Hoac:

1. Vao menu `Chi phi`.
2. Chon dong chi phi.
3. Bam `Ho so can co`.

### Tra cuu tai khoan ke toan

1. Vao menu `Tai khoan`.
2. Nhap so hieu tai khoan hoac tu khoa, vi du: 152, 154, nhan cong, may thi cong.
3. Xem ten tai khoan, loai tai khoan va mo ta.

## 7. Cac file da thay doi

- `database/__init__.py`
- `modules/accounting.py`
- `modules/invoices.py`
- `modules/compliance.py`
- `ui/dialogs.py`
- `ui/main_window.py`

## 8. De xuat buoc tiep theo

- Them man hinh quan ly danh muc du an va danh muc chi phi de nguoi dung tu them/sua/xoa.
- Them chuc nang xem danh sach file dinh kem cua tung chi phi va mo file truc tiep.
- Bo sung day du he thong tai khoan cap 2/cap 3 theo nhu cau doanh nghiep.
- Them mapping tu loai chi phi sang tai khoan goi y, vi du:
  - Vat lieu xay dung -> 621/152
  - Nhan cong -> 622/334
  - May thi cong -> 623
  - Chi phi chung cong trinh -> 627
- Them trang canh bao chi phi thieu chung tu.
