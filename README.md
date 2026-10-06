# TacticalPredict Web App

Aplikasi web Flask untuk memprediksi pertandingan sepak bola berdasarkan pemain yang dipilih untuk dua tim. Aplikasi menghitung probabilitas menang/seri, estimasi gol, skor yang paling mungkin, daftar pencetak gol potensial, dan sensitivitas faktor pertandingan.

## Kebutuhan

- Python 3.10 atau lebih baru
- pip
- Ruang disk yang cukup untuk database pemain dan file model di repository ini

## Menjalankan secara lokal

> **Penting:** repository ini berisi source code, belum berupa situs yang di-host secara online. Alamat `http://127.0.0.1:5000` hanya dapat dibuka di komputer yang menjalankan server aplikasi. Membuka alamat itu langsung dari chat tidak akan menyalakan server.

1. Clone repository dan masuk ke folder project:

   ```bash
   git clone git@github.com:skripsiPredikSepakBola/WebApp.git
   cd WebApp
   ```

   Jika SSH belum diatur, gunakan URL HTTPS dari halaman GitHub repository.

2. Pastikan interpreter yang dipakai Python 3.10 atau lebih baru. Contoh di bawah memakai Python 3.11. Periksa dulu dengan `python3.11 --version` (macOS/Linux) atau `py -3.11 --version` (Windows). Jika belum terpasang, pasang Python 3.11 terlebih dahulu.

   Buat dan aktifkan virtual environment dari interpreter tersebut:

   **macOS / Linux**

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows PowerShell**

   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Pasang dependency:

   ```bash
   python --version
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Jalankan server:

   ```bash
   python app.py
   ```

   Jika port 5000 sedang dipakai program lain, jalankan di port 5001:

   **macOS / Linux**

   ```bash
   PORT=5001 python app.py
   ```

   **Windows PowerShell**

   ```powershell
   $env:PORT = "5001"
   python app.py
   ```

5. Buka `http://127.0.0.1:5000` di browser, atau `http://127.0.0.1:5001` jika memakai port 5001. Hentikan server dengan `Ctrl+C`.

Aplikasi membaca database pemain, preset, dan model relatif terhadap lokasi `app.py`. Biarkan file aset di root repository dan jangan menjalankan aplikasi dari folder lain dengan memindahkan file-file tersebut.

## Cara memakai aplikasi

1. Isi nama tim kandang dan tandang.
2. Pilih pemain untuk starting XI kedua tim; pemain dapat dicari dari database yang tersedia.
3. Tambahkan pemain cadangan bila diperlukan dan atur form tim.
4. Klik tombol prediksi untuk melihat probabilitas hasil, prediksi gol/skor, pencetak gol potensial, metrik tim, dan panel faktor pertandingan.

## API lokal

- `GET /api/players` — daftar pemain.
- `GET /api/presets` — preset susunan pemain.
- `GET /api/categories` — kategori preset.
- `POST /api/predict` — membuat prediksi dari susunan pemain.

Contoh request minimum untuk `POST /api/predict`:

```json
{
  "home_name": "Home FC",
  "away_name": "Away FC",
  "home_starters": [{"id": 123, "name": "Player One", "slot_pos": "GK"}],
  "home_subs": [],
  "away_starters": [{"id": 456, "name": "Player Two", "slot_pos": "GK"}],
  "away_subs": [],
  "home_form_pts": 1.8,
  "away_form_pts": 1.8
}
```

Request produksi UI mengirim pemain sebagai objek yang berisi `id`, `name`, dan `slot_pos`. `home_form_pts` dan `away_form_pts` opsional; nilai default masing-masing adalah `1.8`. Endpoint mengembalikan JSON. Untuk hasil yang bermakna, kirim susunan pemain lengkap sesuai formasi yang diinginkan.

## Isi repository

| Path | Keterangan |
| --- | --- |
| `app.py` | Flask app, pemuatan aset, kalkulasi fitur tim, prediksi, dan endpoint API. |
| `templates/index.html` | Halaman aplikasi. |
| `static/css/style.css` | Tampilan dan layout. |
| `static/js/app.js` | Interaksi browser dan pemanggilan API. |
| `players_lite.json` | Database pemain yang digunakan aplikasi. |
| `preset_lineups.json`, `preset_categories.json` | Preset susunan pemain dan kategorinya. |
| `model_advanced_*.joblib` | Model prediksi hasil dan expected goals. |
| `advanced_feature_cols.joblib` | Urutan fitur input yang diharapkan model. |
| `requirements.txt` | Dependency Python. |

File model `.joblib` disimpan dengan scikit-learn 1.6.1. Versi ini dipatok di `requirements.txt` karena model scikit-learn tidak dijamin dapat dimuat lintas versi.

## Tentang panel XAI

Panel XAI saat ini menghitung sensitivitas dengan mengubah satu fitur menjadi nol lalu membandingkan ulang probabilitas kemenangan. Ini adalah metode ablation/sensitivity, bukan SHAP; angka yang tampil tidak dimaksudkan sebagai kontribusi aditif yang harus berjumlah ke probabilitas akhir.

## Catatan pengembangan

- Server bawaan Flask cocok untuk pengembangan lokal. Untuk deployment publik, gunakan server WSGI dan konfigurasi hosting yang sesuai.
- File virtual environment, cache Python, file rahasia lokal, dan file editor diabaikan oleh `.gitignore`.
- Repository ini berisi aplikasi web saja; dokumen skripsi dan laporan tidak termasuk.
