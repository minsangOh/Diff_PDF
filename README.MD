 # Diff PDF\_FOR SELIM

**Diff PDF\_FOR SELIM**은 세림전자 개발팀의 업무 효율화를 위해 개발된 고성능 PDF 비교 솔루션입니다.
기존 오픈소스인 **ConfrontaPDF**를 Python으로 포팅하고, **NumPy** 행렬 연산과 **렌더링 분리 구조 Lazy Rendering**를 적용하여 대용량 도면에서도 렉 없는 부드러운 비교 성능을 제공합니다.

## 🚀 주요 기능 (Key Features)

### 1\. 강력한 비교 엔진

  * **Visual Diff (Box Highlight)**:
      * 픽셀 단위로 이미지를 정밀 분석하여 차이점을 붉은색 박스로 시각화합니다.
      * 단순 픽셀 덮어쓰기가 아닌 **반투명 박스(No Outline)** 방식을 사용하여 원본 내용을 가리지 않습니다.
  * **Text Diff**: 텍스트 데이터를 추출하여 문자열 유사도를 분석합니다.

### 2\. 압도적인 성능 최적화

  * **분석과 렌더링의 분리 (Analysis vs Rendering Separation)**:
      * 페이지 로드 시 **단 한 번만** 무거운 비교 연산(NumPy)을 수행하여 차이점 좌표를 캐싱합니다.
      * 줌 인/아웃 시에는 캐싱된 좌표를 기반으로 **가벼운 벡터 드로잉**만 수행하여, 고배율 확대 시에도 끊김 없는(Zero Lag) 성능을 보장합니다.
  * **고속 연산**: NumPy 행렬 연산을 통해 수백만 픽셀 비교 속도를 50배 이상 가속화했습니다.

### 3\. 사용자 편의성 (User Experience)

  * **드래그 앤 드롭 (Drag & Drop)**: 파일 열기 창 없이, PDF 파일을 화면에 끌어다 놓아 즉시 비교합니다.
  * **스마트 줌 & 동기화**:
      * `Ctrl + 마우스 휠`로 부드러운 확대/축소가 가능합니다.
      * 좌우 뷰어가 완벽하게 동기화되어 한쪽을 조작하면 반대쪽도 동일하게 움직입니다.
  * **가로 휠(Thumb Wheel)**: `Shift + 마우스 휠`로 좌우 스크롤이 가능합니다.
  * **시인성 조절**: 하이라이트 박스의 **투명도**를 0%\~100%까지 실시간으로 조절할 수 있습니다.

## 🛠 기술 스택 (Tech Stack)

  * **Core Logic**: Python 3.x
  * **GUI Framework**: PyQt6 (Custom Widgets for Drag & Zoom)
  * **PDF Engine**: PyMuPDF (fitz)
  * **Image Processing**: Pillow (PIL), NumPy (Matrix Operation)
  * **Build Tool**: PyInstaller

## 📦 설치 및 실행 (Installation)

### 1\. 가상환경 설정 및 라이브러리 설치

```bash
# 가상환경 활성화 후
pip install pymupdf PyQt6 pillow numpy pyinstaller
```

### 2\. 소스 코드 실행

```bash
python diff_pdf.py
```

## 💡 기술적 원리 (Algorithm Pipeline)

1.  **Rasterization (래스터화)**: PyMuPDF를 사용하여 PDF 벡터 데이터를 고해상도 비트맵으로 변환합니다.
2.  **Image Subtraction (차영상 분석)**: `Img A - Img B` 연산을 통해 픽셀 차이 맵(Difference Map)을 생성합니다.
3.  **Grid-based Max Pooling (격자 기반 풀링)**:
      * 이미지를 10x10 픽셀 격자로 나눕니다.
      * **NumPy**를 사용하여 각 격자의 최대 차이값을 고속으로 계산, 임계값을 넘는 '유의미한 차이' 영역의 좌표(x, y, w, h)만 추출합니다.
4.  **Coordinate Caching (좌표 캐싱)**:
      * 추출된 좌표 데이터를 메모리에 저장합니다. (이미지는 메모리 해제)
5.  **Lazy Rendering (지연 렌더링)**:
      * 사용자가 화면을 확대/축소할 때, 저장된 좌표를 현재 배율(Scale)에 맞춰 `QPainter`로 즉시 그려냅니다. 이 방식은 메모리 사용량을 최소화하고 렌더링 속도를 극대화합니다.

## ⚖️ 라이선스 및 저작권 (License)

  * **Developer**: 오민상 프로 (세림전자 와이어하네스 개발팀)
  * **Original Project**: Based on [ConfrontaPDF](https://github.com/lbellonda/ConfrontaPDF) (GPL v2) by Luca Bellonda & DiffPDF by Mark Summerfield.
  * **License**: GPL v2 / **Internal Use Only**

> **Notice**: 본 프로그램은 GPL v2 라이선스를 따르는 오픈소스를 기반으로 제작되었습니다. 사내 업무용(Internal Use)으로 사용하는 경우 소스 코드 공개 의무가 없으나, 외부(타 법인 포함)로 배포 시 해당 주체에게 소스 코드를 함께 제공해야 합니다.

-----

*Copyright © 2026 Selim Electronics Development Team. All rights reserved.*