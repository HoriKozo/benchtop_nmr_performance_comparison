import re
from dataclasses import dataclass
from typing import Optional, Tuple

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
    # header=None として、Excelの行番号をそのまま扱う
    df = pd.read_excel(uploaded_file, header=None)

    # Excel上の行番号は1始まり、pandasは0始まり
    row_product = 2
    row_frequency = 3
    row_sensitivity_value = 4
    row_sensitivity_label = 5
    row_resolution = 6
    row_size = 7
    row_weight = 8
    row_power = 9
    row_temp = 10

    models: list[NMRModel] = []

    # B列以降を製品データとして読む
    for col in range(1, df.shape[1]):
        product_name = clean_text(df.iat[row_product, col])
        if not product_name:
            continue

        size_text = clean_text(df.iat[row_size, col])
        weight_text = clean_text(df.iat[row_weight, col])
        width_cm, depth_cm, height_cm = parse_size_cm(size_text)
        weight_kg = parse_weight_kg(weight_text)

        model = NMRModel(
            product_name=product_name,
            frequency=clean_text(df.iat[row_frequency, col]),
            sensitivity_value=to_float(df.iat[row_sensitivity_value, col]),
            sensitivity_label=clean_text(df.iat[row_sensitivity_label, col]),
            resolution=clean_text(df.iat[row_resolution, col]),
            resolution_hz=to_float(df.iat[row_resolution, col]),
            size_text=size_text,
            weight_text=weight_text,
            power=clean_text(df.iat[row_power, col]),
            environment_temp=clean_text(df.iat[row_temp, col]),
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

uploaded_file = st.file_uploader(
    "製品情報Excelをアップロードしてください",
    type=["xlsx"],
)

if uploaded_file is None:
    st.info("Excelをアップロードすると、Spinsolve各モデルと競合例をプルダウンから選択できます。")
    st.stop()

models = load_models_from_excel(uploaded_file)

if not models:
    st.error("Excelから製品情報を読み取れませんでした。3行目以降の構造をご確認ください。")
    st.stop()

st.sidebar.header("比較条件")
base_time_min = st.sidebar.number_input(
    "基準機種の測定時間（分）",
    min_value=0.01,
    value=10.0,
    step=1.0,
)

st.sidebar.caption("例：60 MHz機で10分測定した場合、比較機種では何分相当かを計算します。")

col_a, col_b = st.columns(2)
with col_a:
    model_a = get_selected_model("基準機種 A", models)
with col_b:
    model_b = get_selected_model("比較機種 B", models)

if not model_a.sensitivity_value or not model_b.sensitivity_value:
    st.error("感度の数値が不足しています。Excelの5行目、または任意入力値をご確認ください。")
    st.stop()

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
