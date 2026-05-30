import re
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


# ============================================================
# 卓上NMR 測定時間・設置性 比較アプリ 叩き台
# ------------------------------------------------------------
# 前提Excel構造：
#   3行目: 製品名
#   4行目: 動作周波数
#   5行目: 感度 1H（計算用の数値）
#   6行目: 感度 1H アプリ表記（プルダウン・表示用）
#   7行目: 分解能
#   8行目: サイズ
#   9行目: 重量
#   10行目: 電源
#   11行目: 設置環境温度
# ============================================================

st.set_page_config(
    page_title="卓上NMR 測定時間・設置性 比較ツール",
    layout="wide",
)


@dataclass
class NMRModel:
    product_name: str
    frequency: str
    sensitivity_value: Optional[float]
    sensitivity_label: str
    resolution: str
    resolution_hz: Optional[float]
    size_text: str
    weight_text: str
    power: str
    environment_temp: str
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    is_custom: bool = False

    @property
    def volume_l(self) -> Optional[float]:
        if self.width_cm and self.depth_cm and self.height_cm:
            return self.width_cm * self.depth_cm * self.height_cm / 1000
        return None

    @property
    def footprint_cm2(self) -> Optional[float]:
        if self.width_cm and self.depth_cm:
            return self.width_cm * self.depth_cm
        return None

    @property
    def display_name(self) -> str:
        if self.sensitivity_label:
            return f"{self.product_name}｜{self.sensitivity_label}"
        return self.product_name


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_float(value) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", text)
    if not match:
        return None
    return float(match.group(0))


def parse_size_cm(size_text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    例：'58 x 43 x 40 cm' から width, depth, height を抽出。
    x, ×, X に対応。
    """
    if not size_text:
        return None, None, None

    normalized = size_text.lower().replace("×", "x")
    nums = re.findall(r"[0-9]+(?:\.[0-9]+)?", normalized)
    if len(nums) < 3:
        return None, None, None
    return float(nums[0]), float(nums[1]), float(nums[2])


def parse_weight_kg(weight_text: str) -> Optional[float]:
    return to_float(weight_text)


@st.cache_data
def load_models_from_excel(uploaded_file) -> list[NMRModel]:
    """
    Excelから製品情報を読み取る。

    対応形式：
    1) 新形式：周波数ブロックごとに CLASSIC / PLUS / ULTRA が横並び
    2) 旧形式：3行目=製品名、5行目=感度数値、6行目=感度表示、7行目=分解能
    """
    df = pd.read_excel(uploaded_file, header=None)

    def safe_value(row: int, col: int):
        if row < 0 or col < 0:
            return None
        if row >= df.shape[0] or col >= df.shape[1]:
            return None
        return df.iat[row, col]

    def safe_text(row: int, col: int) -> str:
        return clean_text(safe_value(row, col))

    def make_model(
        product_name,
        frequency,
        sensitivity_label,
        sensitivity_value,
        resolution_text,
        category="",
        size_text="",
        weight_text="",
        power="",
        environment_temp="",
    ) -> Optional[NMRModel]:
        product_name = clean_text(product_name)
        if not product_name:
            return None

        sensitivity_num = to_float(sensitivity_value)
        if sensitivity_num is None:
            sensitivity_num = to_float(sensitivity_label)

        if sensitivity_num is None:
            return None

        sensitivity_label = clean_text(sensitivity_label)
        if not sensitivity_label:
            sensitivity_label = f"{sensitivity_num:g}:1"

        full_name = product_name
        if category and category not in product_name:
            full_name = f"{product_name} ({category})"

        width_cm, depth_cm, height_cm = parse_size_cm(size_text)
        weight_kg = parse_weight_kg(weight_text)

        return NMRModel(
            product_name=full_name,
            frequency=frequency,
            sensitivity_value=sensitivity_num,
            sensitivity_label=sensitivity_label,
            resolution=resolution_text,
            resolution_hz=to_float(resolution_text),
            size_text=size_text,
            weight_text=weight_text,
            power=power or "100V",
            environment_temp=environment_temp or "14-28 ℃",
            width_cm=width_cm,
            depth_cm=depth_cm,
            height_cm=height_cm,
            weight_kg=weight_kg,
        )

    models: list[NMRModel] = []

    category_blocks = [
        {"category": "CLASSIC", "product_col": 3, "label_col": 4, "value_col": 5},
        {"category": "PLUS", "product_col": 7, "label_col": 8, "value_col": 9},
        {"category": "ULTRA", "product_col": 11, "label_col": 12, "value_col": 13},
    ]

    # ============================================================
    # 新形式への対応
    # ------------------------------------------------------------
    # B列に 60MHz / 80MHz / 90MHz / 100MHz、
    # C列に Resolution が入る行を、周波数ブロックの開始行として扱う。
    # 製品名に含まれる "Spinsolve 60 MHz" などは拾わない。
    # ============================================================
    frequency_rows: list[int] = []
    for row in range(df.shape[0]):
        frequency_cell = safe_text(row, 1)
        marker_cell = safe_text(row, 2).lower()

        if re.search(r"^(60|80|90|100)\s*MHz$", frequency_cell, flags=re.IGNORECASE) and "resolution" in marker_cell:
            frequency_rows.append(row)

    if frequency_rows:
        for i, freq_row in enumerate(frequency_rows):
            frequency_cell = safe_text(freq_row, 1)
            freq_match = re.search(r"(60|80|90|100)\s*MHz", frequency_cell, flags=re.IGNORECASE)
            frequency = f"{freq_match.group(1)} MHz" if freq_match else frequency_cell

            next_freq_row = frequency_rows[i + 1] if i + 1 < len(frequency_rows) else df.shape[0]

            for block in category_blocks:
                category = block["category"]
                product_col = block["product_col"]
                label_col = block["label_col"]
                value_col = block["value_col"]

                resolution_text = safe_text(freq_row, product_col)

                weight_text = ""
                size_text = ""
                for meta_row in range(freq_row + 1, next_freq_row):
                    marker = safe_text(meta_row, 2).lower()
                    if marker == "weight":
                        weight_text = safe_text(meta_row, product_col)
                    elif marker == "size":
                        size_text = safe_text(meta_row, product_col)

                for row in range(freq_row + 1, next_freq_row):
                    product_name = safe_text(row, product_col)
                    if not product_name:
                        continue

                    marker = safe_text(row, 2).lower()
                    if marker in ["weight", "size"]:
                        continue

                    product_name_lower = product_name.lower()
                    if product_name_lower in ["classic", "plus", "ultra", "product", "model"]:
                        continue
                    if "sensitivity" in product_name_lower or "感度" in product_name_lower:
                        continue

                    model = make_model(
                        product_name=product_name,
                        frequency=frequency,
                        sensitivity_label=safe_text(row, label_col),
                        sensitivity_value=safe_value(row, value_col),
                        resolution_text=resolution_text,
                        category=category,
                        size_text=size_text,
                        weight_text=weight_text,
                    )

                    if model:
                        models.append(model)

        if models:
            return models

    # ============================================================
    # 旧形式へのフォールバック
    # ------------------------------------------------------------
    # Excel上の行番号は1始まり、pandasは0始まり
    # ============================================================
    row_product = 2
    row_frequency = 3
    row_sensitivity_value = 4
    row_sensitivity_label = 5
    row_resolution = 6
    row_size = 7
    row_weight = 8
    row_power = 9
    row_temp = 10

    for col in range(1, df.shape[1]):
        product_name = safe_text(row_product, col)
        if not product_name:
            continue

        size_text = safe_text(row_size, col)
        weight_text = safe_text(row_weight, col)
        width_cm, depth_cm, height_cm = parse_size_cm(size_text)
        weight_kg = parse_weight_kg(weight_text)

        sensitivity_num = to_float(safe_value(row_sensitivity_value, col))
        sensitivity_label = safe_text(row_sensitivity_label, col)

        if sensitivity_num is None:
            sensitivity_num = to_float(sensitivity_label)

        if sensitivity_num is None:
            continue

        if not sensitivity_label:
            sensitivity_label = f"{sensitivity_num:g}:1"

        model = NMRModel(
            product_name=product_name,
            frequency=safe_text(row_frequency, col),
            sensitivity_value=sensitivity_num,
            sensitivity_label=sensitivity_label,
            resolution=safe_text(row_resolution, col),
            resolution_hz=to_float(safe_value(row_resolution, col)),
            size_text=size_text,
            weight_text=weight_text,
            power=safe_text(row_power, col) or "100V",
            environment_temp=safe_text(row_temp, col) or "14-28 ℃",
            width_cm=width_cm,
            depth_cm=depth_cm,
            height_cm=height_cm,
            weight_kg=weight_kg,
        )
        models.append(model)

    return models


def build_custom_model(prefix: str) -> NMRModel:
    st.markdown(f"#### {prefix}：任意入力")

    product_name = st.text_input(f"{prefix} 製品名", value=f"任意入力モデル {prefix}")
    frequency = st.text_input(f"{prefix} 周波数", value="")
    sensitivity_value = st.number_input(
        f"{prefix} ^1H感度（例：240 → 240:1）",
        min_value=1.0,
        value=200.0,
        step=10.0,
    )
    st.markdown(
        '<span style="color:red; font-weight:bold;">'
        '↑この感度値は、PFGを含む実用的な測定条件を前提とした値ですか？'
        '</span>',
    unsafe_allow_html=True,
    )       

    col1, col2, col3 = st.columns(3)
    with col1:
        width_cm = st.number_input(f"{prefix} 幅 cm", min_value=0.0, value=0.0, step=1.0)
    with col2:
        depth_cm = st.number_input(f"{prefix} 奥行 cm", min_value=0.0, value=0.0, step=1.0)
    with col3:
        height_cm = st.number_input(f"{prefix} 高さ cm", min_value=0.0, value=0.0, step=1.0)

    weight_kg = st.number_input(f"{prefix} 重量 kg", min_value=0.0, value=0.0, step=1.0)

    return NMRModel(
        product_name=product_name,
        frequency=frequency,
        sensitivity_value=sensitivity_value,
        sensitivity_label=f"{sensitivity_value:g}:1",
        resolution="任意入力",
        resolution_hz=None,
        size_text=f"{width_cm:g} x {depth_cm:g} x {height_cm:g} cm" if width_cm and depth_cm and height_cm else "任意入力",
        weight_text=f"{weight_kg:g} kg" if weight_kg else "任意入力",
        power="任意入力",
        environment_temp="任意入力",
        width_cm=width_cm if width_cm > 0 else None,
        depth_cm=depth_cm if depth_cm > 0 else None,
        height_cm=height_cm if height_cm > 0 else None,
        weight_kg=weight_kg if weight_kg > 0 else None,
        is_custom=True,
    )


def calc_required_time(base_time_min: float, base_sensitivity: float, target_sensitivity: float) -> float:
    """
    同じS/Nを得るための測定時間目安。
    NMRのS/Nは概ね sqrt(time) に比例すると考え、
    測定時間は感度比の2乗に反比例するとする。
    """
    return base_time_min * (base_sensitivity / target_sensitivity) ** 2


def format_min(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value < 1:
        return f"{value:.2f} 分（約{value * 60:.0f} 秒）"
    return f"{value:.2f} 分"


def ratio_text(value: Optional[float], unit: str = "倍") -> str:
    if value is None:
        return "-"
    return f"{value:.2f}{unit}"


def resolution_comment(model_a: NMRModel, model_b: NMRModel) -> str:
    """
    分解能はHz値が小さいほど高分解能として扱う。
    """
    if model_a.resolution_hz is None or model_b.resolution_hz is None:
        return "分解能の数値比較には、両機種の分解能欄にHz表記の数値が必要です。"

    if model_a.resolution_hz == model_b.resolution_hz:
        return "両機種の分解能は同等です。"

    better = model_a if model_a.resolution_hz < model_b.resolution_hz else model_b
    worse = model_b if better is model_a else model_a
    ratio = worse.resolution_hz / better.resolution_hz

    return (
        f"{better.product_name} の方が分解能値が小さく、ピーク分離の面で有利です。"
        f"数値上は約 {ratio:.2f} 倍の差があります。"
    )


def draw_size_comparison_3d(model_a: NMRModel, model_b: NMRModel):
    """
    幅・奥行・高さを3D直方体として比較表示する。
    実寸比を保った概念図であり、装置形状の正確な外観を示すものではない。
    """
    if not all([model_a.width_cm, model_a.depth_cm, model_a.height_cm, model_b.width_cm, model_b.depth_cm, model_b.height_cm]):
        st.info("3Dサイズ比較には、両機種の幅・奥行・高さ cm が必要です。")
        return

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    models_for_plot = [
        ("A", model_a, 0),
        ("B", model_b, max(model_a.width_cm, model_b.width_cm) * 1.35),
    ]

    max_x = 0
    max_y = 0
    max_z = 0

    for label, model, x_offset in models_for_plot:
        width = model.width_cm
        depth = model.depth_cm
        height = model.height_cm

        ax.bar3d(
            x_offset,
            0,
            0,
            width,
            depth,
            height,
            alpha=0.35,
            shade=True,
        )

        ax.text(
            x_offset + width / 2,
            depth / 2,
            height,
            f"{label}\n{model.product_name}\n{width:g}×{depth:g}×{height:g} cm",
            ha="center",
            va="bottom",
        )

        max_x = max(max_x, x_offset + width)
        max_y = max(max_y, depth)
        max_z = max(max_z, height)

    ax.set_xlabel("Width cm")
    ax.set_ylabel("Depth cm")
    ax.set_zlabel("Height cm")
    ax.set_xlim(0, max_x * 1.1)
    ax.set_ylim(0, max_y * 1.2)
    ax.set_zlim(0, max_z * 1.25)
    ax.set_title("Device Size 3D Comparison (Real-size Image)")
    ax.view_init(elev=22, azim=-55)

    st.pyplot(fig)
    st.caption("Approximate real-size cuboid view. Actual device shape, protrusions, and required installation clearance are not reflected.")


def draw_size_overlay_top_view(model_a: NMRModel, model_b: NMRModel):
    """
    幅×奥行の設置面積を上面図で重ね合わせ表示する。
    """
    if not all([model_a.width_cm, model_a.depth_cm, model_b.width_cm, model_b.depth_cm]):
        st.info("上面図の重ね合わせには、両機種の幅・奥行 cm が必要です。")
        return

    fig, ax = plt.subplots(figsize=(7, 5))

    max_width = max(model_a.width_cm, model_b.width_cm)
    max_depth = max(model_a.depth_cm, model_b.depth_cm)

    # 中心を揃えて重ねる
    a_x = (max_width - model_a.width_cm) / 2
    a_y = (max_depth - model_a.depth_cm) / 2
    b_x = (max_width - model_b.width_cm) / 2
    b_y = (max_depth - model_b.depth_cm) / 2

    rect_a = plt.Rectangle(
        (a_x, a_y),
        model_a.width_cm,
        model_a.depth_cm,
        fill=False,
        linewidth=2,
        label=f"A: {model_a.product_name}",
    )
    rect_b = plt.Rectangle(
        (b_x, b_y),
        model_b.width_cm,
        model_b.depth_cm,
        fill=False,
        linestyle="--",
        linewidth=2,
        label=f"B: {model_b.product_name}",
    )

    ax.add_patch(rect_a)
    ax.add_patch(rect_b)
    ax.set_xlim(-5, max_width + 5)
    ax.set_ylim(-5, max_depth + 5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Width cm")
    ax.set_ylabel("Depth cm")
    ax.set_title("Footprint Overlay - Top View")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    st.pyplot(fig)
    st.caption("The rectangles are center-aligned to compare the required bench footprint. This is an approximate footprint view.")

def extract_frequency_key(model: NMRModel) -> Optional[str]:
    text = f"{model.product_name} {model.frequency}"

    match = re.search(r"(60|80|90|100)\s*MHz", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}MHz"

    for freq in ["100", "90", "80", "60"]:
        if freq in text:
            return f"{freq}MHz"

    return None


def show_image_if_exists(image_path: Path, caption: str):
    if image_path.exists():
        st.image(str(image_path), caption=caption, use_container_width=True)
    else:
        st.info(f"Image not found: {image_path.name}")


def show_ibuprofen_spectrum_examples(model_a: NMRModel, model_b: NMRModel):
    image_dir = Path("assets") / "ibuprofen"

    st.divider()

    full_image_candidates = [
        image_dir / "full_comparison.jpg",
        image_dir / "Ibuprofen-resolution.jpg",
        image_dir / "IIbuprofen -resolution.jpg",
    ]
    full_image_path = next((path for path in full_image_candidates if path.exists()), None)

    header_col, image_col = st.columns([0.36, 0.64])
    with header_col:
        st.header("Ibuprofen Spectrum Example")
        st.caption(
            "Example spectra help visualize how peak separation changes with operating frequency. "
            "These images are reference examples and are not used for numerical calculation."
        )

    with image_col:
        if full_image_path:
            st.image(
                str(full_image_path),
                caption="Full spectrum comparison with highlighted zoom regions",
                use_container_width=True,
            )

    if not image_dir.exists():
        st.info("Image folder not found. Please save spectrum images in assets/ibuprofen.")
        return

    freq_a = None if model_a.is_custom else extract_frequency_key(model_a)
    freq_b = None if model_b.is_custom else extract_frequency_key(model_b)

    st.markdown(
        '### 1H 3.2-3.9 ppm zoom region '
        '<span style="background-color:#d9f3ff; padding:2px 8px; border-radius:6px;">light blue</span>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    for col, model, freq, label in [
        (col1, model_a, freq_a, "A"),
        (col2, model_b, freq_b, "B"),
    ]:
        with col:
            st.markdown(f"#### {label}: {model.product_name}")

            if model.is_custom:
                st.info("Custom model: no ibuprofen spectrum image is displayed.")
                continue

            if not freq:
                st.info("Frequency could not be detected.")
                continue

            image_path = image_dir / f"{freq}_3.6PPM.jpg"
            show_image_if_exists(image_path, f"{label}: {freq} / 1H 3.2-3.9 ppm zoom region")

    st.markdown(
        '### 1H 1.4-2.0 ppm zoom region '
        '<span style="background-color:#dff5df; padding:2px 8px; border-radius:6px;">light green</span>',
        unsafe_allow_html=True,
    )

    col3, col4 = st.columns(2)

    for col, model, freq, label in [
        (col3, model_a, freq_a, "A"),
        (col4, model_b, freq_b, "B"),
    ]:
        with col:
            st.markdown(f"#### {label}: {model.product_name}")

            if not freq:
                st.info("Frequency could not be detected.")
                continue

            image_path = image_dir / f"{freq}.jpg"
            show_image_if_exists(image_path, f"{label}: {freq} / 1H 1.4-2.0 ppm zoom region")


def show_model_card(title: str, model: NMRModel):
    st.markdown(f"### {title}")
    st.write(f"**製品名**：{model.product_name}")
    st.write(f"**周波数**：{model.frequency}")
    st.write(f"**^1H感度**：{model.sensitivity_label} / 計算値 {model.sensitivity_value:g}")
    if model.resolution_hz is not None:
        st.write(f"**分解能**：{model.resolution}（計算値 {model.resolution_hz:g} Hz）")
    else:
        st.write(f"**分解能**：{model.resolution}")
    st.write(f"**サイズ**：{model.size_text}")
    st.write(f"**重量**：{model.weight_text}")
    st.write(f"**電源**：{model.power}")
    st.write(f"**設置環境温度**：{model.environment_temp}")
    if model.is_custom:
        st.caption("※このモデルは任意入力値に基づく参考比較です。")


def get_selected_model(label: str, models: list[NMRModel]) -> NMRModel:
    options = [m.display_name for m in models] + ["任意入力"]
    selected = st.selectbox(label, options)

    if selected == "任意入力":
        return build_custom_model(label)

    selected_index = options.index(selected)
    return models[selected_index]


st.title("卓上NMR 測定時間・設置性 比較ツール")
st.caption("^1H感度から、同等S/Nを得るための測定時間目安を比較します。")

default_data_path = Path("data") / "Spinsolve_Comparison_Table.xlsx"

if not default_data_path.exists():
    st.error(
        "Default data file not found. Please place the Excel file at "
        "data/Spinsolve_Comparison_Table.xlsx."
    )
    st.stop()

models = load_models_from_excel(default_data_path)

if not models:
    st.error("Excelから製品情報を読み取れませんでした。新形式または旧形式のExcel構造をご確認ください。")
    st.stop()

st.sidebar.header("比較条件")
base_time_min = st.sidebar.number_input(
    "基準機種の測定時間（分）",
    min_value=0.01,
    value=10.0,
    step=1.0,
)

st.sidebar.caption("例：60 MHz機で10分測定した場合、比較機種では何分相当かを計算します。")
st.sidebar.divider()

st.sidebar.markdown("### 比較時の重要事項")

st.sidebar.info(

    "本ツールは、主に ^1H感度と^1Hスペクトル例に基づき、測定時間と分解能の違いを理解するための参考ツールです。\n\n"
    "NMR装置の性能比較では、MHz値やカタログ上の最高感度値だけでなく、核種、測定条件、モデル構成、分解能条件を揃えて比較することが重要です。\n\n"
    "特に多核測定や2D測定では、^1H単独の結果だけでは判断できない場合があります。"

)

st.sidebar.markdown(

    """

**1. モデル選択について**  
Magritek Spinsolveは、60 / 80 / 90 / 100 MHzの構成があります。  
用途、核種、分解能、設置性を踏まえてモデルを選択してください。
お気軽にご相談ください。

**2. 感度比較について**  
感度仕様は、測定条件・核種・モデル構成を揃えて比較する必要があります。  
カタログ上の最高感度値だけで比較すると、実運用での測定時間差を正しく判断できない場合があります。

Spinsolveの感度値は、2Dプロトン測定（例えば2D-COSYなど）を前提とした実用的な測定条件値です。
単純な1Dプロトン測定のみを前提とした最高感度値とは、測定条件が異なる場合があります。

**3. 分解能について**  
NMR性能はMHz値だけで決まるものではありません。  
ピーク分離性、線幅、溶媒ピーク近傍の確認などには、分解能性能も重要です。

**4. 測定時間について**  
同等S/Nを得るための測定時間は、感度比の2乗で変化します。  
例：140:1 と 110:1 の比較では、110:1側は約1.6倍の測定時間が必要になります。

**5. モデル名称について**

XX MHz  
1H・19F測定に対応する基本構成です。

XX MHz X-nuclei  
1H・19Fに加えて、2ndチャンネルに任意の観測核を"1種"追加できます。

XX MHz Multi-X  
1H・19Fに加えて、2ndチャンネルに"2〜3種"の観測核を実装できます。

XX MHz Multi-Xn  
1H・19Fに加えて、2ndチャンネルに"4種"以上の観測核を実装できます。
"""

)

st.sidebar.caption(

    "注：本ツールの計算結果は目安です。実際の結果は、核種、サンプル濃度、測定条件、積算回数、分解能設定、溶媒、温度安定性などにより変動します。"

)
col_a, col_b = st.columns(2)
with col_a:
    model_a = get_selected_model("基準機種 A", models)
with col_b:
    model_b = get_selected_model("比較機種 B", models)

if not model_a.sensitivity_value or not model_b.sensitivity_value:
    st.error("感度の数値が不足しています。Excelの5行目、または任意入力値をご確認ください。")
    st.stop()

st.info(
    "注：性能の低いモデルまたは参照モデルをA、性能の高い比較モデルをBとして選択してください。"
    "機種Bの感度が機種Aよりも低い場合、推定測定時間が増加、短縮率が負になります。"
    
    "Note: Select the lower-performance or reference model as A, and the higher-performance comparison model as B. "
    "If B has lower sensitivity than A, the estimated measurement time will increase and the reduction rate may become negative."
)

if model_b.sensitivity_value < model_a.sensitivity_value:
    st.warning(
        "B has lower ^1H sensitivity than A. In this case, the estimated measurement time for B will be longer than A, "
        "so the measurement time reduction rate will be negative."
    )

required_time_b = calc_required_time(
    base_time_min=base_time_min,
    base_sensitivity=model_a.sensitivity_value,
    target_sensitivity=model_b.sensitivity_value,
)

required_time_a_from_b = calc_required_time(
    base_time_min=base_time_min,
    base_sensitivity=model_b.sensitivity_value,
    target_sensitivity=model_a.sensitivity_value,
)

speed_factor = base_time_min / required_time_b if required_time_b else None
reduction_pct = (1 - required_time_b / base_time_min) * 100

st.divider()
st.header("測定時間比較")

m1, m2, m3, m4 = st.columns(4)
m1.metric("基準測定時間", format_min(base_time_min))
m2.metric("比較機種Bの測定時間目安", format_min(required_time_b))
m3.metric("測定時間短縮率", f"{reduction_pct:.1f}%")
m4.metric("処理能力目安", ratio_text(speed_factor))

st.markdown(
    f"""
**{model_a.product_name}** で **{base_time_min:g}分** 必要な測定は、  
**{model_b.product_name}** では **{format_min(required_time_b)}** が目安です。

計算式：  
`比較側測定時間 = 基準測定時間 × (基準感度 / 比較側感度)^2`
"""
)


if model_a.is_custom or model_b.is_custom:
    st.warning("任意入力モデルを含むため、この比較は入力値に基づく参考値です。")

st.divider()
st.header("分解能比較")

resolution_ratio = None
if model_a.resolution_hz and model_b.resolution_hz:
    resolution_ratio = model_b.resolution_hz / model_a.resolution_hz

r1, r2, r3 = st.columns(3)
r1.metric("A：分解能", f"{model_a.resolution_hz:g} Hz" if model_a.resolution_hz else model_a.resolution)
r2.metric("B：分解能", f"{model_b.resolution_hz:g} Hz" if model_b.resolution_hz else model_b.resolution)
r3.metric("分解能比 B/A", ratio_text(resolution_ratio) if resolution_ratio else "-")

st.markdown(resolution_comment(model_a, model_b))
st.caption("注：分解能は一般にHz値が小さいほどピーク分離の面で有利です。ただし、実際のピーク分離や定量性は、サンプル濃度、溶媒、温度安定性、測定条件、線幅、処理条件にも依存します。")
show_ibuprofen_spectrum_examples(model_a, model_b)


st.divider()
st.header("製品情報")
info_a, info_b = st.columns(2)
with info_a:
    show_model_card("基準機種 A", model_a)
with info_b:
    show_model_card("比較機種 B", model_b)

st.divider()
st.header("サイズ・重量比較")

volume_ratio = None
footprint_ratio = None
weight_ratio = None

if model_a.volume_l and model_b.volume_l:
    volume_ratio = model_b.volume_l / model_a.volume_l
if model_a.footprint_cm2 and model_b.footprint_cm2:
    footprint_ratio = model_b.footprint_cm2 / model_a.footprint_cm2
if model_a.weight_kg and model_b.weight_kg:
    weight_ratio = model_b.weight_kg / model_a.weight_kg

c1, c2, c3 = st.columns(3)
c1.metric("体積比 B/A", ratio_text(volume_ratio))
c2.metric("設置面積比 B/A", ratio_text(footprint_ratio))
c3.metric("重量比 B/A", ratio_text(weight_ratio))

size_df = pd.DataFrame(
    [
        {
            "項目": "基準機種 A",
            "製品名": model_a.product_name,
            "幅 cm": model_a.width_cm,
            "奥行 cm": model_a.depth_cm,
            "高さ cm": model_a.height_cm,
            "体積 L": model_a.volume_l,
            "設置面積 cm²": model_a.footprint_cm2,
            "重量 kg": model_a.weight_kg,
        },
        {
            "項目": "比較機種 B",
            "製品名": model_b.product_name,
            "幅 cm": model_b.width_cm,
            "奥行 cm": model_b.depth_cm,
            "高さ cm": model_b.height_cm,
            "体積 L": model_b.volume_l,
            "設置面積 cm²": model_b.footprint_cm2,
            "重量 kg": model_b.weight_kg,
        },
    ]
)

st.dataframe(size_df, use_container_width=True)

st.subheader("Size Comparison")
view_mode = st.radio(
    "表示方法",
    ["3D Size Comparison", "Footprint Overlay", "Ratio Summary"],
    horizontal=True,
)

if view_mode == "3D Size Comparison":
    draw_size_comparison_3d(model_a, model_b)

elif view_mode == "Footprint Overlay":
    draw_size_overlay_top_view(model_a, model_b)

else:
    st.markdown("### Ratio Summary")
    st.caption("B / A comparison based on actual dimensions and weight.")

    ratio_df = pd.DataFrame(
        [
            {
                "項目": "体積比",
                "倍率": volume_ratio,
            },
            {
                "項目": "設置面積比",
                "倍率": footprint_ratio,
            },
            {
                "項目": "重量比",
                "倍率": weight_ratio,
            },
        ]
    )

    st.dataframe(ratio_df, use_container_width=True)

    ratio_chart_df = ratio_df.set_index("項目")
    st.bar_chart(ratio_chart_df)

    st.markdown(
        f"""
- 体積比 B/A：**{ratio_text(volume_ratio)}**
- 設置面積比 B/A：**{ratio_text(footprint_ratio)}**
- 重量比 B/A：**{ratio_text(weight_ratio)}**
"""
    )

st.divider()
st.header("処理能力の目安")

operation_hours = st.number_input("1日の測定稼働時間（時間）", min_value=0.5, value=8.0, step=0.5)
operation_min = operation_hours * 60
samples_a = operation_min / base_time_min
samples_b = operation_min / required_time_b if required_time_b else None

p1, p2, p3 = st.columns(3)
p1.metric("A：1日あたり測定数", f"{samples_a:.1f} 検体")
p2.metric("B：1日あたり測定数", f"{samples_b:.1f} 検体" if samples_b else "-")
p3.metric("増加分", f"{(samples_b - samples_a):.1f} 検体/日" if samples_b else "-")

st.caption(
    "注：本計算は、同等S/Nを得るための測定時間目安です。実際の測定時間は、サンプル濃度、核種、パルス条件、積算回数、分解能設定、溶媒、温度安定性などにより変動します。"
)
