# Selim PDF Diff Tool (Diff PDF_FOR SELIM)

**Selim PDF Diff**는 세림전자 개발팀의 업무 효율화를 위해 개발된 고성능 PDF 비교 데스크탑 애플리케이션입니다.
기존 오픈소스의 한계를 넘어, **Python(PyQt6)** 로 포팅하고 **NumPy 행렬 연산**과 **Lazy Rendering(지연 렌더링)** 기법을 독자적으로 적용하여 대용량 도면 비교 시에도 끊김 없는(Zero-Lag) 성능을 제공합니다.

---

## 🚀 핵심 기능 (Key Features)

### 1. 강력한 비교 엔진 (High-Performance Engine)
* **Visual Diff (Box Highlight)**:
    * 픽셀 단위 정밀 분석을 통해 차이점을 **붉은색 반투명 박스**로 시각화합니다.
    * **Image Subtraction & Grid Pooling** 알고리즘을 적용하여 노이즈를 배제하고 유의미한 차이만 검출합니다.
* **Text Diff**: 문서 내 텍스트 데이터를 추출하여 문자열 유사도(Sequence Matcher)를 분석합니다.

### 2. 압도적인 성능 최적화 (Optimization)
* **분석과 렌더링의 분리 (Analysis vs Rendering Separation)**:
    * 페이지 로드 시 **NumPy**를 활용해 단 한 번만 무거운 비교 연산을 수행하고 좌표를 캐싱합니다.
    * 줌/패닝 시에는 캐싱된 좌표를 기반으로 가벼운 벡터 드로잉만 수행하여 500% 확대 시에도 프레임 저하가 없습니다.
* **고속 연산**: Python의 느린 반복문을 배제하고 NumPy 벡터 연산을 활용해 픽셀 처리 속도를 약 50배 가속화했습니다.

### 3. 사용자 경험 (UX/UI)
* **Smart Sync**: 좌우 뷰어가 완벽하게 동기화되어, 한쪽을 스크롤/줌 하면 반대쪽도 동일하게 움직입니다.
* **Drag & Drop**: 파일 열기 대화상자 없이 파일을 드래그하여 즉시 로드합니다.
* **Overlay Control**: 하이라이트 박스의 투명도(Opacity)를 실시간으로 조절하여 원본 내용을 쉽게 확인할 수 있습니다.

---

## 🛠 기술 스택 (Tech Stack)

| Category | Technology | Usage |
| :--- | :--- | :--- |
| **Language** | Python 3.13 | Core Logic |
| **GUI** | PyQt6 | User Interface (Custom Widgets) |
| **PDF Engine** | PyMuPDF (fitz) | Rendering & Text Extraction |
| **Data/Img** | NumPy, Pillow | Matrix Operation, Image Processing |
| **Build** | PyInstaller | Single Executable Packaging |

---

## 📂 프로젝트 구조 (Project Structure)

```text
Diff_PDF/
├── core/
│   └── engine.py       # PDF 로딩, NumPy 기반 이미지 비교 알고리즘
├── ui/
│   ├── main_window.py  # 메인 윈도우 및 이벤트 핸들러
│   └── widgets.py      # 커스텀 위젯 (DropLabel, SyncedScrollArea)
├── utils/
│   └── helpers.py      # 리소스 경로 처리 (PyInstaller 대응)
├── main.py             # 애플리케이션 엔트리 포인트
├── Diff_PDF.spec       # PyInstaller 빌드 설정 파일
└── requirements.txt    # 의존성 패키지 목록
```

---

# 📦 설치 및 빌드 (Installation)

## 의존성 설치
```bash
pip install -r requirements.txt
```

## 소스 코드 실행
```bash
python main.py
```

## 실행파일 다운로드 경로
https://github.com/minsangOh/Diff_PDF/releases

---

## 💡 알고리즘 파이프라인 (Algorithm Pipeline)
### Rasterization
PyMuPDF로 PDF를 비트맵 이미지로 변환

### Subtraction:
Img A - Img B 연산으로 Difference Map 생성

### Grid Pooling (NumPy):
이미지를 5x5 격자로 분할 후 Max Pooling 수행

임계값을 초과하는 격자의 좌표(x, y, w, h)만 추출하여 메모리에 캐싱

Lazy Drawing: QPainter를 사용하여 현재 줌 레벨에 맞춰 캐싱된 좌표에 박스를 실시간 드로잉

---

## ⚖️ 라이선스 (License)
Developer: 오민상 (Selim Electronics Development Team)

Base Project: Inspired by ConfrontaPDF & DiffPDF.

Notice: 본 프로그램은 사내 업무용(Internal Use Only)으로 제작되었습니다.

Copyright © 2026 Selim Electronics Development Team. All rights reserved.